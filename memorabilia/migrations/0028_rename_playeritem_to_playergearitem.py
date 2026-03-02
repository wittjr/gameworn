"""
Rename PlayerItem → PlayerGearItem and PlayerItemImage → PlayerGearItemImage.

The main table (playeritem) can be renamed with a simple ALTER TABLE — SQLite 3.26+
automatically updates FK references in other tables (photomatch), and MySQL/Postgres
rename the constraints too.

The image table (playeritemimage) must be recreated rather than renamed because we
create a new PlayerItemImage table in migration 0030. If we just renamed the old table,
SQLite would keep the old index name (memorabilia_playeritemimage_collectible_id_...)
and migration 0030's CreateModel would fail with "index already exists".
"""

import django.db.models.deletion
from django.db import migrations, models


def rename_image_table_forward(apps, schema_editor):
    db = schema_editor.connection.vendor
    if db == 'sqlite':
        schema_editor.execute("PRAGMA foreign_keys = OFF")
        schema_editor.execute(
            "ALTER TABLE memorabilia_playeritem RENAME TO memorabilia_playergearitem"
        )
        schema_editor.execute("""
            CREATE TABLE memorabilia_playergearitemimage (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "primary" bool NULL,
                image varchar(100) NULL,
                link varchar(255) NULL,
                "flickrObject" text NULL,
                collectible_id integer NOT NULL
                    REFERENCES memorabilia_playergearitem(id)
                    DEFERRABLE INITIALLY DEFERRED
            )
        """)
        schema_editor.execute(
            "INSERT INTO memorabilia_playergearitemimage "
            "SELECT * FROM memorabilia_playeritemimage"
        )
        schema_editor.execute("DROP TABLE memorabilia_playeritemimage")
        schema_editor.execute("PRAGMA foreign_keys = ON")
    else:
        # MySQL / PostgreSQL: rename both tables; FK references are preserved
        schema_editor.execute(
            "ALTER TABLE memorabilia_playeritem RENAME TO memorabilia_playergearitem"
        )
        schema_editor.execute(
            "ALTER TABLE memorabilia_playeritemimage RENAME TO memorabilia_playergearitemimage"
        )


def rename_image_table_backward(apps, schema_editor):
    db = schema_editor.connection.vendor
    if db == 'sqlite':
        schema_editor.execute("PRAGMA foreign_keys = OFF")
        schema_editor.execute(
            "ALTER TABLE memorabilia_playergearitem RENAME TO memorabilia_playeritem"
        )
        schema_editor.execute("""
            CREATE TABLE memorabilia_playeritemimage (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "primary" bool NULL,
                image varchar(100) NULL,
                link varchar(255) NULL,
                "flickrObject" text NULL,
                collectible_id integer NOT NULL
                    REFERENCES memorabilia_playeritem(id)
                    DEFERRABLE INITIALLY DEFERRED
            )
        """)
        schema_editor.execute(
            "INSERT INTO memorabilia_playeritemimage "
            "SELECT * FROM memorabilia_playergearitemimage"
        )
        schema_editor.execute("DROP TABLE memorabilia_playergearitemimage")
        schema_editor.execute("PRAGMA foreign_keys = ON")
    else:
        schema_editor.execute(
            "ALTER TABLE memorabilia_playergearitem RENAME TO memorabilia_playeritem"
        )
        schema_editor.execute(
            "ALTER TABLE memorabilia_playergearitemimage RENAME TO memorabilia_playeritemimage"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0027_otheritem_otheritemimage'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel('PlayerItem', 'PlayerGearItem'),
                migrations.RenameModel('PlayerItemImage', 'PlayerGearItemImage'),
            ],
            database_operations=[
                migrations.RunPython(
                    rename_image_table_forward,
                    rename_image_table_backward,
                ),
            ],
        ),
    ]
