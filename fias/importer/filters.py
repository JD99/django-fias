# coding: utf-8
from __future__ import unicode_literals, absolute_import


def example_filter_accept(item):
    """
    Всегда разрешает импорт записи
    :param item:
    :return item or None:
    """
    return item


def example_filter_reject(item):
    """
    Всегда запрещает импорт записи
    :param item:
    :return item or None:
    """
    return None
