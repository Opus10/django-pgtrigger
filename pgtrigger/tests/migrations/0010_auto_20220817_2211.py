# Generated by Django 3.2.15 on 2022-08-17 22:11

import psqlextra.backend.migrations.operations.add_default_partition
import psqlextra.backend.migrations.operations.create_partitioned_model
import psqlextra.manager.manager
import psqlextra.models.partitioned
import psqlextra.types
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tests", "0009_orderschema_receiptschema"),
    ]

    operations = [
        psqlextra.backend.migrations.operations.create_partitioned_model.PostgresCreatePartitionedModel(  # noqa
            name="PartitionModel",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.TextField()),
                ("timestamp", models.DateTimeField()),
            ],
            options={
                "abstract": False,
                "base_manager_name": "objects",
            },
            partitioning_options={
                "method": psqlextra.types.PostgresPartitioningMethod["RANGE"],
                "key": ["timestamp"],
            },
            bases=(psqlextra.models.partitioned.PostgresPartitionedModel,),
            managers=[
                ("objects", psqlextra.manager.manager.PostgresManager()),
            ],
        ),
        psqlextra.backend.migrations.operations.add_default_partition.PostgresAddDefaultPartition(
            model_name="PartitionModel",
            name="default",
        ),
    ]
