
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase


class AuthenticationTest(APITestCase):
    def test_user_cannot_sign_up_with_password_mismatch(self):
        #given
        data ={
            'first_name':'First name',
            'last_name':'Last name',
            'username': 'username1',
            'password1': 'password',
            'password2': 'password1',
            'email':'email@email.com'
        }
        
        #when
        response = self.client.post(reverse('sign-up'),data=data)
        #then
        user = get_user_model().objects.last()
        self.assertEqual(user, None)
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        
    def test_user_cannot_sign_up_with_same_email(self):
        #given
        data2 = data ={
            'first_name':'First name',
            'last_name':'Last name',
            'username': 'username1',
            'password1': 'password',
            'password2': 'password',
            'email':'email@email.com'
        }
    
        data2['email'] = 'email@email.com'
        data2['username'] = 'username2'
    
        self.client.post(reverse('sign-up'),data=data)
        response_client_2 = self.client.post(reverse('sign-up'),data=data2)

        #then
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response_client_2.status_code)
        
    def test_user_can_sign_up(self):
        #given
        data ={
            'first_name':'First name',
            'last_name':'Last name',
            'username': 'username1',
            'password1': 'password-test',
            'password2': 'password-test',
            'email':'email@email.com'
        }
        
        #when
        response = self.client.post(reverse('sign-up'),data=data)
        #then
        user = get_user_model().objects.last()
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(response.data['id'], user.id)
        self.assertEqual(response.data['username'], user.username)
        self.assertEqual(response.data['first_name'], user.first_name)
        self.assertEqual(response.data['last_name'], user.last_name)