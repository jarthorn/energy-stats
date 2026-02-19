from django.test import TestCase
from core.models import Fuel


class FuelModelTests(TestCase):
    def test_create_fuel(self):
        """A Fuel can be created and its fields retrieved correctly."""
        fuel = Fuel.objects.create(
            type="Solar",
            rank=3,
            summary="Solar power converts sunlight directly into electricity via photovoltaic cells.",
        )
        self.assertEqual(fuel.type, "Solar")
        self.assertEqual(fuel.rank, 3)
        self.assertEqual(str(fuel), "Solar")

    def test_fuel_type_is_unique(self):
        """Two Fuel rows cannot share the same type string."""
        Fuel.objects.create(type="Wind", rank=2, summary="Wind energy summary.")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Fuel.objects.create(type="Wind", rank=99, summary="Duplicate.")
