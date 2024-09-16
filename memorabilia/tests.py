from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib import auth
from .models import Collection, Collectible

# Create your tests here.
class CollectionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admintest', password='12345', is_superuser=True)
        cls.testuser = User.objects.create_user(username='testuser', password='12345')
        Collection.objects.create(owner_uid=cls.testuser.id, title='existing collection')

    def setUp(self):
        pass

    def test_create_owned_collection(self):
        c = Client()
        user = User.objects.create_user(username='testuser2', password='12345', is_superuser=False)
        authorized = c.login(username='testuser2', password='12345')
        u = auth.get_user(c)
        collection = Collection.objects.create(owner_uid=u.id, title='create test collection')
        self.assertEqual(collection.owner_uid, user.id)
        self.assertEqual(collection.title, 'create test collection')

    def test_modify_owned_collection_title(self):
        c = Client()
        user = User.objects.create_user(username='testuser2', password='12345', is_superuser=False)
        authorized = c.login(username='testuser2', password='12345')
        u = auth.get_user(c)
        collection = Collection.objects.create(owner_uid=u.id, title='create test collection')
        self.assertEqual(collection.owner_uid, user.id)
        self.assertEqual(collection.title, 'create test collection')
        collection.title = 'new title'
        self.assertEqual(collection.title, 'new title')

    def test_modify_owned_collection_owner(self):
        c = Client()
        user = User.objects.create_user(username='testuser2', password='12345', is_superuser=False)
        authorized = c.login(username='testuser2', password='12345')
        u = auth.get_user(c)
        collection = Collection.objects.create(owner_uid=u.id, title='create test collection')
        self.assertEqual(collection.owner_uid, user.id)
        self.assertEqual(collection.title, 'create test collection')
        collection.owner_uid = self.testuser.id
        self.assertEqual(collection.owner_uid, u.id)

    def test_delete_owned_collection(self):
        pass

    def test_create_nonowned_collection(self):
        pass

    def test_modify_nonowned_collection(self):
        pass
    
    def test_delete_nonowned_collection(self):
        pass
    
    def test_superuser_create_owned_collection(self):
        pass
    
    def test_superuser_modify_owned_collection(self):
        pass
    
    def test_superuser_delete_owned_collection(self):
        pass
    
    def test_superuser_create_nonowned_collection(self):
        pass
    
    def test_superuser_modify_nonowned_collection(self):
        pass
    
    def test_superuser_delete_nonowned_collection(self):
        pass
    
