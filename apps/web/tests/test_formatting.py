from django.template import Context, Template
from django.test import SimpleTestCase, override_settings


class WebFormattingTests(SimpleTestCase):
    @override_settings(LANGUAGE_CODE="en-us")
    def test_money_filter_uses_currency_code_without_hardcoded_symbol(self):
        rendered = Template("{% load web_format %}{{ 123456|money_from_cents:'EUR' }}").render(
            Context()
        )
        self.assertEqual(rendered, "EUR 1,234.56")

    def test_money_filter_handles_invalid_input(self):
        rendered = Template("{% load web_format %}{{ value|money_from_cents:'usd' }}").render(
            Context({"value": "invalid"})
        )
        self.assertEqual(rendered, "USD 0.00")
