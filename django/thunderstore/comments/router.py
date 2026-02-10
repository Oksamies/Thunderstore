class CommentsRouter:
    """
    A router to control all database operations on models in the
    thunderstore.comments application.
    """

    route_app_labels = {"comments"}
    db_name = "comments"

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
        Allow relations if both models are in the comments app.
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
        Make sure the comments app only appears in the 'comments' database.
        And other apps do not appear in the 'comments' database.
        """
        if app_label in self.route_app_labels:
            return db == self.db_name

        # Allow contenttypes to migrate to comments DB
        if app_label == "contenttypes":
            return True

        elif db == self.db_name:
            # Prevent other apps from migrating to comments db
            return False
        return None
