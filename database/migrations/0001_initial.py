from tortoise import migrations
from tortoise.migrations import operations as ops
from sillo.record.fields import CreatedAtField, SoftDeleteField, UpdatedAtField
from tortoise import fields

class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name='AdminActivity',
            fields=[
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('created_at', CreatedAtField()),
                ('updated_at', UpdatedAtField()),
                ('deleted_at', SoftDeleteField(null=True)),
                ('user_email', fields.CharField(max_length=255)),
                ('action', fields.CharField(max_length=50)),
                ('model_name', fields.CharField(max_length=100)),
                ('object_id', fields.CharField(null=True, max_length=50)),
                ('detail', fields.TextField(null=True, unique=False)),
                ('ip_address', fields.CharField(null=True, max_length=50)),
                ('user_agent', fields.TextField(null=True, unique=False)),
            ],
            options={'table': 'admin_activity', 'app': 'models', 'pk_attr': 'id', 'table_description': 'Tracks every admin action for audit purposes.'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='User',
            fields=[
                ('created_at', CreatedAtField()),
                ('updated_at', UpdatedAtField()),
                ('deleted_at', SoftDeleteField(null=True)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('email', fields.CharField(unique=True, db_index=True, max_length=255)),
                ('username', fields.CharField(unique=True, db_index=True, max_length=150)),
                ('password', fields.CharField(max_length=128)),
                ('is_active', fields.BooleanField(default=True)),
                ('is_staff', fields.BooleanField(default=False)),
                ('is_superuser', fields.BooleanField(default=False)),
                ('last_login', fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                ('email_verified_at', fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                ('full_name', fields.CharField(null=True, max_length=150)),
            ],
            options={'table': 'users', 'app': 'models', 'pk_attr': 'id', 'table_description': 'A person who can sign in to Starter.'},
            bases=['UserBaseModel'],
        ),
    ]
