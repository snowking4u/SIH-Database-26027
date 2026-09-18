"""STEP 11 planning-level synthesis: resources, task-resource links,
task dependencies.

Resources use deterministic ``SYN-RES-*`` codes with a synthetic-capacity pool.
Task-resource and dependency relations stay inside the one deterministic layer
that already generates planning tasks from maintenance requirements.
"""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.planning_resource import PlanningResource
from app.models.planning_task import PlanningTask
from app.models.task_dependency import TaskDependency
from app.models.task_resource import TaskResource

from . import random_utils as ru
from .config import MARKER, SyntheticConfig

RESOURCE_TYPES = ["TRACK_ENGINEER", "MAINTAINER", "POWER_SUPPLY", "TRACK_MACHINE"]
RESOURCE_STATUSES = ["AVAILABLE", "AVAILABLE", "UNAVAILABLE", "UNDER_MAINTENANCE"]
ALLOCATION_STATUSES = ["ALLOCATED", "REQUIRED", "REQUIRED"]
DEPENDENCY_TYPE = "PRECEDENCE"


class PlanningGenerator:
    def __init__(self, db: Session, cfg: SyntheticConfig, rng: random.Random):
        self.db = db
        self.cfg = cfg
        self.rng = rng

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
                    capacity=float(ru.int_between(self.rng, 1, 8)),
                    unit="units",
                    status=ru.pick(self.rng, RESOURCE_STATUSES),
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
        if not tasks:
            return 0, 0
        resource_ids = list(
            self.db.scalars(
                select(PlanningResource.id).order_by(PlanningResource.id)
            ).all()
        )
        if not resource_ids:
            return 0, 0
        created = skipped = 0
        for task in tasks:
            links = []
            for offset in range(1, 3):
                pick_id = resource_ids[(task.id + offset) % len(resource_ids)]
                resource = self.db.get(PlanningResource, pick_id)
                if resource is None:
                    continue
                link = self.db.scalar(
                    select(TaskResource).where(
                        TaskResource.planning_task_id == task.id,
                        TaskResource.planning_resource_id == resource.id,
                    )
                )
                if link is not None:
                    skipped += 1
                    continue
                if resource.status in ("UNAVAILABLE", "UNDER_MAINTENANCE"):
                    allocation = "UNAVAILABLE"
                else:
                    allocation = ru.pick(self.rng, ALLOCATION_STATUSES)
                links.append(
                    TaskResource(
                        planning_task_id=task.id,
                        planning_resource_id=resource.id,
                        required_quantity=ru.int_between(self.rng, 1, 3),
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
        created = skipped = 0
        for i, task in enumerate(tasks):
            if i + 1 >= len(tasks):
                break
            if not ru.rand_boolean(self.rng, self.cfg.dependency_rate):
                continue
            successor = tasks[i + 1]
            existing = self.db.scalar(
                select(TaskDependency).where(
                    TaskDependency.predecessor_task_id == task.id,
                    TaskDependency.successor_task_id == successor.id,
                    TaskDependency.dependency_type == DEPENDENCY_TYPE,
                )
            )
            if existing is not None:
                skipped += 1
                continue
            self.db.add(
                TaskDependency(
                    predecessor_task_id=task.id,
                    successor_task_id=successor.id,
                    dependency_type=DEPENDENCY_TYPE,
                    lag_minutes=ru.int_between(self.rng, 30, 240),
                    description=f"{MARKER} synthetic task precedence dependency.",
                )
            )
            created += 1
        return created, skipped