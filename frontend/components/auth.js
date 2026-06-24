// AUTHENTICATION COMPONENT (SIGNUP/LOGIN)
import { fetchAPI, setToken, setUserName } from '../api.js';

export function initAuth(onSuccessCallback) {
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const authError = document.getElementById('auth-error');
    
    const toggleToSignup = document.getElementById('toggle-to-signup');
    const toggleToLogin = document.getElementById('toggle-to-login');
    
    // Toggle login/signup forms view
    toggleToSignup.addEventListener('click', () => {
        loginForm.classList.add('hidden');
        signupForm.classList.remove('hidden');
        authError.classList.add('hidden');
    });
    
    toggleToLogin.addEventListener('click', () => {
        signupForm.classList.add('hidden');
        loginForm.classList.remove('hidden');
        authError.classList.add('hidden');
    });
    
    // Handle Login Form Submit
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        authError.classList.add('hidden');
        
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        
        try {
            const data = await fetchAPI('/login', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            });
            
            if (data.status === 'success') {
                setToken(data.token);
                setUserName(data.name);
                onSuccessCallback();
            }
        } catch (err) {
            authError.textContent = err.message || 'Login failed. Please check credentials.';
            authError.classList.remove('hidden');
        }
    });
    
    // Handle Signup Form Submit
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        authError.classList.add('hidden');
        
        const name = document.getElementById('signup-name').value;
        const email = document.getElementById('signup-email').value;
        const password = document.getElementById('signup-password').value;
        
        try {
            const data = await fetchAPI('/signup', {
                method: 'POST',
                body: JSON.stringify({ name, email, password })
            });
            
            if (data.status === 'success') {
                setToken(data.token);
                setUserName(data.name);
                onSuccessCallback();
            }
        } catch (err) {
            authError.textContent = err.message || 'Signup failed. Please try again.';
            authError.classList.remove('hidden');
        }
    });
}
