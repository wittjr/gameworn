from django.test import TestCase


class CIGateVerificationTests(TestCase):
    """Scratch test to confirm the required 'test' status check blocks a merge.

    This file is deliberately temporary — see issue #128 criterion 3 — and
    will be removed once the branch protection gate is verified.
    """

    def test_deliberately_fails(self):
        self.assertTrue(False, "Deliberate failure to verify CI gate blocks merge")
