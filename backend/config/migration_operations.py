from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class AddIndexConcurrently(migrations.AddIndex):
    """Create PostgreSQL indexes without blocking writes during an upgrade."""

    atomic = False

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if not self.allow_migrate_model(schema_editor.connection.alias, model):
            return
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.add_index(model, self.index, concurrently=True)
            return
        if not isinstance(self.index, GinIndex):
            schema_editor.add_index(model, self.index)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        if not self.allow_migrate_model(schema_editor.connection.alias, model):
            return
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.remove_index(model, self.index, concurrently=True)
            return
        if not isinstance(self.index, GinIndex):
            schema_editor.remove_index(model, self.index)
