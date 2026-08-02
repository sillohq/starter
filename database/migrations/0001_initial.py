import functools
from json import dumps, loads

from sillo.record.fields import CreatedAtField, PasswordField, SoftDeleteField, UpdatedAtField
from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name="AdminActivity",
            fields=[
                (
                    "id",
                    fields.IntField(generated=True, primary_key=True, unique=True, db_index=True),
                ),
                ("created_at", CreatedAtField()),
                ("updated_at", UpdatedAtField()),
                ("deleted_at", SoftDeleteField(null=True)),
                ("user_email", fields.CharField(max_length=255)),
                ("action", fields.CharField(max_length=50)),
                ("model_name", fields.CharField(max_length=100)),
                ("object_id", fields.CharField(null=True, max_length=50)),
                ("detail", fields.TextField(null=True, unique=False)),
                ("ip_address", fields.CharField(null=True, max_length=50)),
                ("user_agent", fields.TextField(null=True, unique=False)),
            ],
            options={
                "table": "admin_activity",
                "app": "models",
                "pk_attr": "id",
                "table_description": "Tracks every admin action for audit purposes.",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="AdminRole",
            fields=[
                (
                    "id",
                    fields.IntField(generated=True, primary_key=True, unique=True, db_index=True),
                ),
                ("created_at", CreatedAtField()),
                ("updated_at", UpdatedAtField()),
                ("deleted_at", SoftDeleteField(null=True)),
                ("name", fields.CharField(unique=True, max_length=100)),
                ("slug", fields.CharField(unique=True, max_length=100)),
                (
                    "permissions",
                    fields.JSONField(
                        default=list,
                        encoder=functools.partial(dumps, separators=(",", ":")),
                        decoder=loads,
                    ),
                ),
                ("description", fields.TextField(null=True, unique=False)),
            ],
            options={
                "table": "admin_roles",
                "app": "models",
                "pk_attr": "id",
                "table_description": "RBAC role for admin users.",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="AdminUser",
            fields=[
                ("created_at", CreatedAtField()),
                ("updated_at", UpdatedAtField()),
                ("deleted_at", SoftDeleteField(null=True)),
                (
                    "id",
                    fields.IntField(generated=True, primary_key=True, unique=True, db_index=True),
                ),
                ("email", fields.CharField(unique=True, db_index=True, max_length=255)),
                ("username", fields.CharField(unique=True, db_index=True, max_length=150)),
                ("password", PasswordField(max_length=255)),
                ("is_active", fields.BooleanField(default=True)),
                ("is_staff", fields.BooleanField(default=False)),
                ("is_superuser", fields.BooleanField(default=False)),
                ("last_login", fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                (
                    "email_verified_at",
                    fields.DatetimeField(null=True, auto_now=False, auto_now_add=False),
                ),
                (
                    "role",
                    fields.ForeignKeyField(
                        "models.AdminRole",
                        source_field="role_id",
                        null=True,
                        db_constraint=True,
                        to_field="id",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "admin_users",
                "app": "models",
                "pk_attr": "id",
                "table_description": "Admin user with role-based access control.",
            },
            bases=["UserBaseModel"],
        ),
        ops.CreateModel(
            name="User",
            fields=[
                ("created_at", CreatedAtField()),
                ("updated_at", UpdatedAtField()),
                ("deleted_at", SoftDeleteField(null=True)),
                (
                    "id",
                    fields.IntField(generated=True, primary_key=True, unique=True, db_index=True),
                ),
                ("email", fields.CharField(unique=True, db_index=True, max_length=255)),
                ("username", fields.CharField(unique=True, db_index=True, max_length=150)),
                ("password", fields.CharField(max_length=128)),
                ("is_active", fields.BooleanField(default=True)),
                ("is_staff", fields.BooleanField(default=False)),
                ("is_superuser", fields.BooleanField(default=False)),
                ("last_login", fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                (
                    "email_verified_at",
                    fields.DatetimeField(null=True, auto_now=False, auto_now_add=False),
                ),
                ("full_name", fields.CharField(null=True, max_length=150)),
            ],
            options={
                "table": "users",
                "app": "models",
                "pk_attr": "id",
                "table_description": "A person who can sign in to Starter.",
            },
            bases=["UserBaseModel"],
        ),
    ]
