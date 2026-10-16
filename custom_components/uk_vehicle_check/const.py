from datetime import timedelta

DOMAIN = "uk_vehicle_check"

CONF_REGISTRATION = "registration"

CONF_DUE_SOON_DAYS = "due_soon_days"

DEFAULT_DUE_SOON_DAYS = 28

# DVLA is checked at most once a day per vehicle; a failed check is retried
# at the next update interval.
CHECK_EVERY = timedelta(hours=24)

UPDATE_INTERVAL = timedelta(hours=6)

STORAGE_VERSION = 1
