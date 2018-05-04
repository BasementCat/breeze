import unittest

from breeze.plugins.base import MergedDict, Plugin


class TestMergedDict(unittest.TestCase):
    def test_init(self):
        d = MergedDict()

        self.assertEqual([d.changes], d.dicts)
        self.assertEqual({}, d.changes)
        self.assertEqual([], d.deletions)

    def test_init__dicts(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        self.assertEqual([d.changes, a, b], d.dicts)
        self.assertEqual({}, d.changes)
        self.assertEqual([], d.deletions)

    def test_str_repr(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        s = str(d)
        r = repr(d)

        self.assertEqual(s, r)
        # No direct equality test here, order of keys in a dict is nondeterministic
        # Could use ordered dicts...
        self.assertTrue('foo' in s)
        self.assertTrue('bar' in s)
        self.assertTrue('baz' in s)
        self.assertTrue('quux' in s)
        self.assertTrue('foo' in r)
        self.assertTrue('bar' in r)
        self.assertTrue('baz' in r)
        self.assertTrue('quux' in r)

    def test_len(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        self.assertEqual(2, len(d))

        d['sldkfksjld'] = 'lkljsdjfklsd'
        self.assertEqual(3, len(d))

    def test_getitem_setitem_delitem_contains(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        self.assertEqual('bar', d['foo'])
        self.assertEqual('quux', d['baz'])

        with self.assertRaises(KeyError):
            d['sldkfksjld']

        d['sldkfksjld'] = 'lkljsdjfklsd'
        self.assertEqual('lkljsdjfklsd', d['sldkfksjld'])

        self.assertEqual(1, len(a))
        self.assertEqual(1, len(b))

        del d['baz']
        with self.assertRaises(KeyError):
            d['baz']

        self.assertEqual(1, len(a))
        self.assertEqual(1, len(b))

        self.assertTrue('foo' in d)
        self.assertFalse('baz' in d)
        self.assertTrue('sldkfksjld' in d)

    def test_get(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        self.assertEqual('bar', d.get('foo'))
        self.assertEqual('bar', d.get('asdfsd', 'bar'))
        self.assertIsNone(d.get('asdfsd'))

    def test_set(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        d.set('bar', 'foo')
        self.assertEqual('foo', d.get('bar'))

    def test_setdefault(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        d.setdefault('foo', 'alskdjflk')
        d.setdefault('bar', 'foo')
        self.assertEqual('foo', d.get('bar'))
        self.assertEqual('bar', d.get('foo'))

    def test_keys(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        self.assertEqual(['foo', 'baz'], d.keys())

    def test_values(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        self.assertEqual(['bar', 'quux'], d.values())

    def test_items(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        self.assertEqual([('foo', 'bar'), ('baz', 'quux')], d.items())

    def test_update(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        d.update({'a': 'b'})
        self.assertEqual('b', d['a'])

    def test_merge_changes(self):
        a = {'foo': 'bar'}
        b = {'baz': 'quux'}
        d = MergedDict(a, b)

        d['a'] = 'b'
        res = d.merge_changes()

        self.assertEqual({'foo': 'bar'}, a)
        self.assertEqual({'baz': 'quux', 'a': 'b'}, b)
        self.assertTrue(b is res)


class TestPlugin(unittest.TestCase):
    def test_init(self):
        p = Plugin()
        self.assertEqual({}, p.additional_context)
        self.assertEqual({}, p.file_data)

        p = Plugin(context={'foo': 'bar'}, file_data={'baz': 'quux'})
        self.assertEqual({'foo': 'bar'}, p.additional_context)
        self.assertEqual({'baz': 'quux'}, p.file_data)

    def test_run(self):
        class MockPlugin(Plugin):
            def _run(self):
                self.mark_matched('foo')
                self.delete('bar')
                self.context['a'] = 'b'

        class MockBreeze(object):
            context = {'q': 'w'}
            files = {
                'foo': {'u': 'i'},
                'bar': {'o': 'p'},
                'baz': {'a': 's'},
            }

        p = MockPlugin(context={'e': 'r'}, file_data={'t': 'y'})
        p.run(MockBreeze())

        self.assertEqual({'q': 'w', 'a': 'b'}, MockBreeze.context)
        self.assertEqual(
            {
                'foo': {'u': 'i', 't': 'y'},
                'baz': {'a': 's'}
            },
            MockBreeze.files
        )