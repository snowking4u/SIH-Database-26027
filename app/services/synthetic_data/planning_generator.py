"""STEP 11 planning-level synthesis: resources, task-resource links,
task dependencies.

Every assignment here is a pure deterministic function of the row ids and the
run seed (no sequential RNG draws), so re-running over an already-populated
database reproduces exactly the same links and only skips existing ones.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.planning_resource import PlanningResource
from app.models.planning_task import PlanningTask
from app.models.task_dependency import TaskDependency
from app.models.task_resource import TaskResource

from .config import MARKER, SyntheticConfig

RESOURCE_TYPES = ["TRACK_ENGINEER", "MAINTAINER", "POWER_SUPPLY", "TRACK_MACHINE"]
RESOURCE_STATUSES = ["AVAILABLE", "AVAILABLE", "UNAVAILABLE", "UNDER_MAINTENANCE"]
ALLOCATION_STATUSES = ["ALLOCATED", "REQUIRED", "REQUIRED"]
DEPENDENCY_TYPE = "PRECEDENCE"


class PlanningGenerator:
    def __init__(self, db: Session, cfg: SyntheticConfig):
        self.db = db
        self.cfg = cfg

    def generate(self) -> dict:
        stats = {"resources_created": 0, "task_resources_created": 0,
                 "task_resources_skipped": 0, "dependencies_created": 0,
                 "dependencies_skipped": 0}
        stats["resources_created"] = self._generate_resources()
        stats["task_resources_created"], stats["task_resources_skipped"] = (
            self._generate_task_resources()
        )
        stats["dependencies_created"], stats["dependencies_skipped"] = (
            self._generate_dependencies()
        )
        self.db.commit()
        return stats

    # ------------------------------------------------------------------ #
    # Pure deterministic helpers
    # ------------------------------------------------------------------ #
    def _has_dependency(self, i: int) -> bool:
        rate = self.cfg.dependency_rate
        if rate >= 1.0:
            return True
        bucket = (self.cfg.seed * 1000003 + i * 7919) % 97
        return bucket < rate * 97

    def _lag_minutes(self, i: int) -> int:
        return (i * 13 % 211) + 30

    # ------------------------------------------------------------------ #
    def _generate_resources(self) -> int:
        existing = set(
            self.db.scalars(
                select(PlanningResource.resource_code).where(
                    PlanningResource.resource_code.startswith("SYN-RES-")
                )
            ).all()
        )
        created = 0
        resources: list[PlanningResource] = []
        for n in range(self.cfg.resource_count):
            code = f"SYN-RES-{n + 1:04d}"
            if code in existing:
                continue
            resources.append(
                PlanningResource(
                    resource_code=code,
                    resource_type=RESOURCE_TYPES[n % len(RESOURCE_TYPES)],
                    resource_name=f"Synthetic Resource {n + 1}",
                    description=f"{MARKER} synthetic planning resource.",
                    capacity=float((n * 7 + 3) % 8 + 1),
                    unit="units",
                    status=RESOURCE_STATUSES[(n * 7 + 3) % len(RESOURCE_STATUSES)],
                    location_code=None,
                )
            )
            created += 1
        if resources:
            self.db.add_all(resources)
            self.db.flush()
        return created

    def _generate_task_resources(self) -> tuple[int, int]:
        tasks = self.db.scalars(
            select(PlanningTask).order_by(PlanningTask.id)
        ).all()
        resource_ids = list(
            self.db.scalars(
                select(PlanningResource.id).order_by(PlanningResource.id)
            ).all()
        )
        if not tasks or not resource_ids:
            return 0, 0
        existing = {
            (planning_task_id, planning_resource_id)
            for planning_task_id, planning_resource_id in self.db.execute(
                select(TaskResource.planning_task_id, TaskResource.planning_resource_id)
            ).all()
        }
        created = skipped = 0
        for task in tasks:
            links: list[TaskResource] = []
            for offset in range(1, 3):
                pick_id = resource_ids[(task.id + offset) % len(resource_ids)]
                if (task.id, pick_id) in existing:
                    skipped += 1
                    continue
                resource = self.db.get(PlanningResource, pick_id)
                if resource is None:
                    continue
                if resource.status in ("UNAVAILABLE", "UNDER_MAINTENANCE"):
                    allocation = "UNAVAILABLE"
                else:
                    allocation = ALLOCATION_STATUSES[(task.id + offset) % len(ALLOCATION_STATUSES)]
                links.append(
                    TaskResource(
                        planning_task_id=task.id,
                        planning_resource_id=resource.id,
                        required_quantity=(task.id * 3 + offset) % 3 + 1,
                        allocation_status=allocation,
                        remarks=f"{MARKER} synthetic task-resource assignment.",
                    )
                )
                created += 1
            if links:
                self.db.add_all(links)
                self.db.flush()
        return created, skipped

    def _generate_dependencies(self) -> tuple[int, int]:
        tasks = self.db.scalars(
            select(PlanningTask).order_by(PlanningTask.id)
        ).all()
        existing = {
            (predecessor_task_id, successor_task_id, dependency_type)
            for predecessor_task_id, successor_task_id, dependency_type in self.db.execute(
                select(
                    TaskDependency.predecessor_task_id,
                    TaskDependency.successor_task_id,
                    TaskDependency.dependency_type,
                )
            ).all()
        }
        created = skipped = 0
        for i, task in enumerate(tasks):
            if i + 1 >= len(tasks):
                break
            if not self._has_dependency(i):
                continue
            successor = tasks[i + 1]
            key = (task.id, successor.id, DEPENDENCY_TYPE)
            if key in existing:
                skipped += 1
                continue
            self.db.add(
                TaskDependency(
                    predecessor_task_id=task.id,
                    successor_task_id=successor.id,
                    dependency_type=DEPENDENCY_TYPE,
                    lag_minutes=self._lag_minutes(i),
                    description=f"{MARKER} synthetic task precedence dependency.",
                )
            )
            created += 1
        return created, skipped