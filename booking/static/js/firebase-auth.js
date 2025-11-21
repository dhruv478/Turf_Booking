// static/js/firebase-auth.js

// 1) Firebase Config
const firebaseConfig = {
  apiKey: "AIzaSyAhfkHFyzJytU0EJ2hbDLehUQsZDfakdu0",
  authDomain: "turf-booking-b9a7c.firebaseapp.com",
  projectId: "turf-booking-b9a7c",
  storageBucket: "turf-booking-b9a7c.firebasestorage.app",
  messagingSenderId: "555875411843",
  appId: "1:555875411843:web:42b42142e9670f5fea78b6",
  measurementId: "G-176VPMPEDC"
};

// Initialize Firebase
if (!window.firebase || !firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}

// CSRF helper (optional)
function getCSRFToken() {
  const name = 'csrftoken';
  const cookie = document.cookie.split(';').find(c => c.trim().startsWith(name + '='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
}

// 2) Google popup login + send token to Django
async function signInWithGoogleAndSendToken() {
  try {
    const provider = new firebase.auth.GoogleAuthProvider();

    // Open Google Popup
    const result = await firebase.auth().signInWithPopup(provider);

    // Get token from Google
    const idToken = await result.user.getIdToken(true);

    // Send token to Django backend
    const resp = await fetch('/api/firebase-login/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),   // optional
      },
      body: JSON.stringify({ token: idToken })
    });

    const data = await resp.json();

    if (resp.ok && data.status === 'ok') {
      // Google login success → redirect to role-based page
      window.location.href = "/auth/google/redirect/";
    } else {
      alert("Login failed: " + (data.error || JSON.stringify(data)));
    }

  } catch (err) {
    console.error("Firebase sign-in error:", err);
    alert("Authentication error: " + err.message);
  }
}
