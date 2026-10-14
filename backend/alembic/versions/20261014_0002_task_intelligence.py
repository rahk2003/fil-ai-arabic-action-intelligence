"""Task intelligence fields and review queue.

Revision ID: 20261014_0002
Revises: 20261014_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20261014_0002"
down_revision = "20261014_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("description", sa.Text()))
    op.add_column(
        "tasks",
        sa.Column("workflow_status", sa.String(30), server_default="pending", nullable=False),
    )
    op.add_column("tasks", sa.Column("original_deadline", sa.String(100)))
    op.execute("UPDATE tasks SET original_deadline = deadline WHERE original_deadline IS NULL")

    op.add_column("task_events", sa.Column("summary", sa.Text()))
    op.add_column(
        "task_events",
        sa.Column("related_message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="SET NULL")),
    )
    op.add_column(
        "task_events",
        sa.Column("model_prediction_id", sa.Integer(), sa.ForeignKey("model_predictions.id", ondelete="SET NULL")),
    )
    op.create_index("ix_task_events_related_message_id", "task_events", ["related_message_id"])
    op.create_index("ix_task_events_model_prediction_id", "task_events", ["model_prediction_id"])

    op.create_table(
        "task_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("model_predictions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("suggestion_type", sa.String(40), nullable=False),
        sa.Column("suggested_title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("current_deadline", sa.String(100)),
        sa.Column("proposed_deadline", sa.String(100)),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("review_status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "suggestion_type IN ('new_task','reschedule','cancellation')",
            name="ck_task_suggestions_type",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending','confirmed','rejected')",
            name="ck_task_suggestions_review_status",
        ),
    )
    op.create_index("ix_task_suggestions_message_id", "task_suggestions", ["message_id"])
    op.create_index("ix_task_suggestions_prediction_id", "task_suggestions", ["prediction_id"])
    op.create_index("ix_task_suggestions_task_id", "task_suggestions", ["task_id"])
    op.create_index(
        "ix_task_suggestions_status_created",
        "task_suggestions",
        ["review_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("task_suggestions")
    op.drop_index("ix_task_events_model_prediction_id", table_name="task_events")
    op.drop_index("ix_task_events_related_message_id", table_name="task_events")
    op.drop_column("task_events", "model_prediction_id")
    op.drop_column("task_events", "related_message_id")
    op.drop_column("task_events", "summary")
    op.drop_column("tasks", "original_deadline")
    op.drop_column("tasks", "workflow_status")
    op.drop_column("tasks", "description")
