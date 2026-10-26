"""TechPark Settings showed 0 for every limit that was never saved (Lock Entries After,
reminder days). Write their defaults (lock 15 days, escalation 3, cold prospect 30,
not visited 60) without touching values already saved; reminders stay as they are."""

from techpark.techpark.doctype.techpark_settings.techpark_settings import fill_defaults


def execute():
	fill_defaults()
