# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import requests
from datetime import datetime, date

import django
from django.test import TestCase
from django.db import models

from . import utils


class MockedResponse(object):
    def __init__(self, status_code, content, headers={}):
        self.status_code = status_code
        self.content = content.encode('utf8')
        self.headers = headers

    def json(self):
        import json
        return json.loads(self.text)

    def raise_for_status(self):
        pass

    @property
    def text(self):
        return self.content.decode('utf8')


class mocked_response:
    def __init__(self, *responses):
        self.responses = list(responses)

    def __enter__(self):
        self.orig_get = requests.get
        self.orig_post = requests.post
        self.orig_request = requests.request

        def mockable_request(f):
            def new_f(*args, **kwargs):
                if self.responses:
                    return self.responses.pop(0)
                return f(*args, **kwargs)
            return new_f
        requests.get = mockable_request(requests.get)
        requests.post = mockable_request(requests.post)
        requests.request = mockable_request(requests.request)

    def __exit__(self, type, value, traceback):
        requests.get = self.orig_get
        requests.post = self.orig_post
        requests.request = self.orig_request


class BasicTests(TestCase):

    def test_generate_unique_username(self):
        examples = [('a.b-c@gmail.com', 'a.b-c'),
                    ('Üsêrnamê', 'username'),
                    ('User Name', 'user_name'),
                    ('', 'user')]
        for input, username in examples:
            self.assertEqual(utils.generate_unique_username([input]),
                             username)

    def test_email_validation(self):
        is_email_max_75 = django.VERSION[:2] <= (1, 7)
        if is_email_max_75:
            s = 'unfortunately.django.user.email.max_length.is.set.to.75.which.is.too.short@bummer.com'  # noqa
            self.assertEqual(None, utils.valid_email_or_none(s))
        s = 'this.email.address.is.a.bit.too.long.but.should.still.validate.ok@short.com'  # noqa
        self.assertEqual(s, utils.valid_email_or_none(s))
        if is_email_max_75:
            s = 'x' + s
            self.assertEqual(None, utils.valid_email_or_none(s))
            self.assertEqual(None, utils.valid_email_or_none("Bad ?"))

    def test_serializer(self):
        class SomeModel(models.Model):
            dt = models.DateTimeField()
            t = models.TimeField()
            d = models.DateField()
        instance = SomeModel(dt=datetime.now(),
                             d=date.today(),
                             t=datetime.now().time())
        instance.nonfield = 'hello'
        data = utils.serialize_instance(instance)
        instance2 = utils.deserialize_instance(SomeModel, data)
        self.assertEqual(instance.nonfield, instance2.nonfield)
        self.assertEqual(instance.d, instance2.d)
        self.assertEqual(instance.dt.date(), instance2.dt.date())
        for t1, t2 in [(instance.t, instance2.t),
                       (instance.dt.time(), instance2.dt.time())]:
            self.assertEqual(t1.hour, t2.hour)
            self.assertEqual(t1.minute, t2.minute)
            self.assertEqual(t1.second, t2.second)
            # AssertionError: datetime.time(10, 6, 28, 705776)
            #     != datetime.time(10, 6, 28, 705000)
            self.assertEqual(int(t1.microsecond / 1000),
                             int(t2.microsecond / 1000))

    @unittest.skipUnless(django.VERSION[:2] >= (1, 6), 'BinaryField was added in Django 1.6')
    def test_serializer_binary_field(self):
        class SomeBinaryModel(models.Model):
            bb = models.BinaryField()
            bb_empty = models.BinaryField()

        instance = SomeBinaryModel(bb=b'some binary data')

        serialized = utils.serialize_instance(instance)
        deserialized = utils.deserialize_instance(SomeBinaryModel, serialized)

        self.assertEqual(serialized['bb'], 'c29tZSBiaW5hcnkgZGF0YQ==')
        self.assertEqual(serialized['bb_empty'], '')
        self.assertEqual(deserialized.bb, b'some binary data')
        self.assertEqual(deserialized.bb_empty, b'')
