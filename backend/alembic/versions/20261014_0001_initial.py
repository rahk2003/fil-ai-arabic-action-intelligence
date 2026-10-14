"""Initial FI'L AI relational schema.

Revision ID: 20261014_0001
Revises: None
"""

from alembic import op
import sqlalchemy as sa

revision = "20261014_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(250)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(80), server_default="local", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("priority", sa.String(20), server_default="medium", nullable=False),
        sa.Column("deadline", sa.String(100)),
        sa.Column("original_message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("model_version", sa.String(150)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','completed','canceled')", name="ck_tasks_status"),
        sa.CheckConstraint("priority IN ('low','medium','high','urgent')", name="ck_tasks_priority"),
    )
    op.create_index("ix_tasks_conversation_id", "tasks", ["conversation_id"])
    op.create_index("ix_tasks_original_message_id", "tasks", ["original_message_id"])
    op.create_index("ix_tasks_status_deadline", "tasks", ["status", "deadline"])
    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text()), sa.Column("new_value", sa.Text()),
        sa.Column("evidence", sa.Text()), sa.Column("confirmed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_task_events_task_created", "task_events", ["task_id", "created_at"])
    op.create_table(
        "model_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version", sa.String(150), nullable=False),
        sa.Column("intent", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float()), sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_predictions_model_intent", "model_predictions", ["model_version", "intent"])
    op.create_index("ix_model_predictions_message_id", "model_predictions", ["message_id"])
    op.create_index("ix_model_predictions_intent", "model_predictions", ["intent"])
    op.create_table(
        "user_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("model_predictions.id", ondelete="SET NULL")),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("corrected_intent", sa.String(40)), sa.Column("corrected_payload_json", sa.Text()),
        sa.Column("reviewer", sa.String(120)), sa.Column("review_status", sa.String(40), server_default="reviewed_candidate", nullable=False),
        sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_corrections_review_status", "user_corrections", ["review_status", "created_at"])
    op.create_index("ix_user_corrections_prediction_id", "user_corrections", ["prediction_id"])
    op.create_index("ix_user_corrections_message_id", "user_corrections", ["message_id"])


def downgrade() -> None:
    op.drop_table("user_corrections")
    op.drop_table("model_predictions")
    op.drop_table("task_events")
    op.drop_table("tasks")
    op.drop_table("messages")
    op.drop_table("conversations")
