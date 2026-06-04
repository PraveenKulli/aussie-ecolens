// src/services/auth.js
import {
  signIn, signOut, signUp, confirmSignUp,
  getCurrentUser, fetchAuthSession,
} from 'aws-amplify/auth';

export async function register({ email, password, firstName, lastName }) {
  return signUp({
    username: email,
    password,
    options: {
      userAttributes: {
        email,
        given_name:  firstName,
        family_name: lastName,
      },
    },
  });
}

export async function confirmEmail(email, code) {
  return confirmSignUp({ username: email, confirmationCode: code });
}

export async function login(email, password) {
  return signIn({ username: email, password });
}

export async function logout() {
  return signOut();
}

export async function getIdToken() {
  const session = await fetchAuthSession();
  return session.tokens?.idToken?.toString() || '';
}

export async function getUser() {
  try {
    return await getCurrentUser();
  } catch {
    return null;
  }
}
