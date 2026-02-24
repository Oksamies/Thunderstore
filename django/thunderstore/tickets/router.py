class TicketsRouter:
    """
    A router to control all database operations on models in the
    thunderstore.tickets application.
    """

    route_app_labels = {"tickets"}
    db_name = "tickets"

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.db_name
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.db_name
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if both models are in the tickets app.
        Also allow relations to ContentType.
        """
        if (
            obj1._meta.app_label in self.route_app_labels
            or obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the tickets app only appears in the 'tickets' database.
        And other apps do not appear in the 'tickets' database.
        """
        import sys

        from django.conf import settings

        is_alias = "pytest" in sys.modules or settings.DATABASES.get(
            self.db_name, {}
        ).get("NAME") == settings.DATABASES.get("default", {}).get("NAME")

        if app_label in self.route_app_labels:
            return db == self.db_name or (is_alias and db == "default")

        # Allow contenttypes to migrate to tickets DB
        if app_label == "contenttypes":
            return True

        elif db == self.db_name:
            # Prevent other apps from migrating to tickets db
            return is_alias
        return None
