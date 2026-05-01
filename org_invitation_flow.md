```text
1. User clicks email link
         ↓
2. Browser opens → yourapp.com/signup?invite_token=abc123xyz
         ↓
3. Frontend reads the token from the URL
   const params = new URLSearchParams(window.location.search)
   const inviteToken = params.get("invite_token")  // "abc123xyz"
         ↓
4. Frontend stores it temporarily
   sessionStorage.setItem("invite_token", inviteToken)
   (just needs to survive until after signup — sessionStorage is enough)
         ↓
5. User fills signup form and submits
         ↓
6. Signup API called → user created → auth token returned
         ↓
7. Frontend reads invite_token from sessionStorage
   if invite_token exists → immediately call POST /invites/accept/
         ↓
8. Membership created → redirect to invited org dashboard
   sessionStorage.removeItem("invite_token")  // clean up