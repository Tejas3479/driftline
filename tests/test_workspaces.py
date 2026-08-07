import uuid

import httpx
import pytest

from main import app
from src.auth.dependencies import get_current_user


@pytest.mark.asyncio
async def test_workspace_user_management():
    # Remove the global mock from conftest.py so we can test real roles
    app.dependency_overrides.pop(get_current_user, None)
    
    unique_id = uuid.uuid4().hex[:8]
    admin_email = f"admin_{unique_id}@acme.com"
    member_email = f"member_{unique_id}@acme.com"
    hacker_email = f"hacker_{unique_id}@acme.com"
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        
        # 1. Register an admin user (this creates a workspace automatically)
        register_res = await client.post("/api/v1/auth/register", json={
            "email": admin_email,
            "password": "password123",
            "workspace_name": f"Acme Corp {unique_id}",
            "role": "admin"
        })
        assert register_res.status_code == 200, f"Registration failed: {register_res.text}"
        admin_data = register_res.json()
        workspace_id = admin_data["workspace_id"]
        
        # Login to get token
        login_res = await client.post("/api/v1/auth/login", data={
            "username": admin_email,
            "password": "password123"
        })
        assert login_res.status_code == 200
        admin_token = login_res.cookies.get("driftline_token")
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        
        # 2. Admin adds a member to the workspace
        add_res = await client.post(
            f"/api/v1/workspaces/{workspace_id}/users",
            json={"email": member_email, "password": "password123", "role": "member"},
            headers=headers_admin
        )
        assert add_res.status_code == 200
        member_id = add_res.json()["id"]
        
        # 3. List workspace users
        list_res = await client.get(
            f"/api/v1/workspaces/{workspace_id}/users",
            headers=headers_admin
        )
        assert list_res.status_code == 200
        assert len(list_res.json()) == 2
        
        # 4. Member login and try to add user (should fail)
        login_member_res = await client.post("/api/v1/auth/login", data={
            "username": member_email,
            "password": "password123"
        })
        member_token = login_member_res.cookies.get("driftline_token")
        headers_member = {"Authorization": f"Bearer {member_token}"}
        
        add_fail_res = await client.post(
            f"/api/v1/workspaces/{workspace_id}/users",
            json={"email": hacker_email, "password": "password123", "role": "admin"},
            headers=headers_member
        )
        assert add_fail_res.status_code == 403
        
        # 5. Admin updates member role to admin
        update_res = await client.patch(
            f"/api/v1/workspaces/users/{member_id}",
            json={"role": "admin"},
            headers=headers_admin
        )
        assert update_res.status_code == 200
        assert update_res.json()["role"] == "admin"
        
        # 6. Admin removes member
        remove_res = await client.delete(
            f"/api/v1/workspaces/users/{member_id}",
            headers=headers_admin
        )
        assert remove_res.status_code == 200
        
        # 7. Admin tries to remove themselves (last admin)
        remove_self_res = await client.delete(
            f"/api/v1/workspaces/users/{admin_data['id']}",
            headers=headers_admin
        )
        assert remove_self_res.status_code == 400
