# -*- coding: utf-8 -*-
import math
from typing import IO, AnyStr, List

import alg
from html import escape
from babel.numbers import format_decimal
from pint import Quantity

from classes import ShoppingListEntry


def format_amount(quantity: Quantity) -> tuple[str, str]:
    """Format a quantity for display in the shopping list.

    Returns a ``(magnitude_str, unit_name)`` pair where ``unit_name`` is the
    Pint unit name (still to be translated via ``alg.translate_unit``).

    Rules:
    - grams < 1000 g -> whole grams
    - grams >= 1000 g -> kilograms, up to 2 decimals (trailing zeros trimmed)
    - count ("st") -> rounded up to whole units (can't buy half a piece)
    - kilograms -> up to 2 decimals (trailing zeros trimmed)
    - anything else -> unchanged 2-decimal rounding
    """
    mag = quantity.magnitude
    unit = str(quantity.units)

    if unit == "gram":
        if mag >= 1000:
            value: float = round(mag / 1000, 2)
            unit = "kilogram"
        else:
            value = round(mag)
    elif unit == "count":
        value = math.ceil(mag)
    elif unit == "kilogram":
        value = round(mag, 2)
    else:
        value = round(mag, 2)

    # Babel's default decimal pattern trims trailing zeros, so rounding above
    # yields "up to N decimals" for free (5.5 -> "5,5", 5.0 -> "5").
    return format_decimal(value, locale="sv_SE"), unit


def shopping_list_to_html5(
    shopping_list: list[ShoppingListEntry], outputfile: IO[AnyStr]
):
    print(
        '<html><head><link rel="stylesheet" href="shopping.css"/><meta http-equiv="content-type" content="text/html; charset=UTF-8" /></head>',
        file=outputfile,
    )
    print("<body>", file=outputfile)
    ingredients: list[ShoppingListEntry]
    for cat, ingredients in sorted(alg.order_by_category(shopping_list)):
        print("<h1>" + escape(cat) + "</h1>", file=outputfile)
        print('<table class="tbl">', file=outputfile)
        print("  <thead>", file=outputfile)
        print(
            '    <tr><th></th><th colspan="2" class="amt">Mängd</th><th class="ingredient">Ingrediens</th><th class="sources">Till</th></tr>',
            file=outputfile,
        )
        print("  </thead>", file=outputfile)
        print("  <tbody>", file=outputfile)
        for ingredient in sorted(ingredients):
            print("  <tr>", file=outputfile)
            print("    <td>&#x25a2;</td>", file=outputfile)
            if ingredient.quantity:
                magnitude_str, unit_name = format_amount(ingredient.quantity)
                print(
                    '    <td class="numeric amt-magnitude">' + magnitude_str + "</td>",
                    file=outputfile,
                )
                print(
                    '    <td class="amt-unit">'
                    + escape(alg.translate_unit(unit_name))
                    + "</td>",
                    file=outputfile,
                )
            else:
                print('    <td colspan="2"></td>', file=outputfile)
            print(
                '    <td class="ingredient">' + escape(ingredient.name) + "</td>",
                file=outputfile,
            )
            print(
                '    <td class="sources">'
                + escape(", ".join([x.dish.name for x in ingredient.sources]))
                + "</td>",
                file=outputfile,
            )
            print("  </tr>", file=outputfile)
        print("  </tbody>", file=outputfile)
        print("</table>", file=outputfile)
    print("</body></html>", file=outputfile)
