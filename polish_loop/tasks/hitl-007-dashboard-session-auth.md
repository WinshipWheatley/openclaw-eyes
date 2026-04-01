title: hitl-007-dashboard-session-auth
goal: Implement basic password or token session protection for the HITL React dashboard.

Description:
Add a minimal authentication guard to the dashboard so only authorized users can view pending approvals and action history. Start with a server-side token check or password-based session gate that blocks unauthenticated access.

Verification:
- Unauthenticated requests to protected dashboard routes are rejected with 401 or redirect to login.
- Authenticated session can load dashboard pages successfully.
- Session expiration or logout removes access until re-authentication.
