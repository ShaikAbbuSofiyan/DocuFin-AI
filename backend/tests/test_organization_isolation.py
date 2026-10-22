import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_organization_isolation_and_rbac(client: AsyncClient):
    # 1. Register User A with Organization Alpha
    res_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@alpha-holdings.com",
            "password": "Password123!",
            "full_name": "Alice Alpha",
            "organization_name": "Alpha Holdings",
        },
    )
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]

    # Retrieve Org A id from /auth/me
    me_a = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    org_a_id = me_a.json()["active_organization_id"]

    # 2. Register User B with Organization Beta
    res_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@beta-capital.com",
            "password": "Password123!",
            "full_name": "Bob Beta",
            "organization_name": "Beta Capital",
        },
    )
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]

    me_b = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    org_b_id = me_b.json()["active_organization_id"]

    assert org_a_id != org_b_id

    # 3. User A creates a document in Org A
    doc_payload = {
        "title": "Alpha Q3 Financial Disclosure",
        "filename": "alpha_q3_10q.pdf",
        "file_size_bytes": 1048576,
        "mime_type": "application/pdf",
        "doc_type": "10-Q",
    }
    doc_create_res = await client.post(
        f"/api/v1/organizations/{org_a_id}/documents",
        json=doc_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert doc_create_res.status_code == 201
    doc_a_id = doc_create_res.json()["id"]

    # 4. User A can view the document in Org A
    get_doc_res = await client.get(
        f"/api/v1/organizations/{org_a_id}/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_doc_res.status_code == 200
    assert get_doc_res.json()["title"] == "Alpha Q3 Financial Disclosure"

    # 5. SECURITY CHECK: User B (from Org B) tries to read Org A's document -> 403 Forbidden
    cross_read_res = await client.get(
        f"/api/v1/organizations/{org_a_id}/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_read_res.status_code == 403
    assert cross_read_res.json()["error"]["code"] == "FORBIDDEN"

    # 6. SECURITY CHECK: User B tries to list Org A's documents -> 403 Forbidden
    cross_list_res = await client.get(
        f"/api/v1/organizations/{org_a_id}/documents",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_list_res.status_code == 403

    # 7. SECURITY CHECK: User B tries to delete Org A's document -> 403 Forbidden
    cross_delete_res = await client.delete(
        f"/api/v1/organizations/{org_a_id}/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_delete_res.status_code == 403

    # 8. User B creates and lists documents in Org B (should only see their own)
    beta_doc_create = await client.post(
        f"/api/v1/organizations/{org_b_id}/documents",
        json={
            "title": "Beta Annual Audit 10-K",
            "filename": "beta_10k.pdf",
            "file_size_bytes": 2097152,
            "mime_type": "application/pdf",
            "doc_type": "10-K",
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert beta_doc_create.status_code == 201

    beta_list_res = await client.get(
        f"/api/v1/organizations/{org_b_id}/documents",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert beta_list_res.status_code == 200
    beta_docs = beta_list_res.json()
    assert len(beta_docs) == 1
    assert beta_docs[0]["title"] == "Beta Annual Audit 10-K"

    # 9. RBAC: User A (Admin) registers User C and adds them to Org A as 'Analyst'
    res_c = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "charlie@alpha-holdings.com",
            "password": "Password123!",
            "full_name": "Charlie Analyst",
        },
    )
    assert res_c.status_code == 201
    token_c = res_c.json()["access_token"]

    # User A adds Charlie as Analyst in Org A
    add_member_res = await client.post(
        f"/api/v1/organizations/{org_a_id}/members",
        json={"email": "charlie@alpha-holdings.com", "role": "Analyst"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert add_member_res.status_code == 201
    assert add_member_res.json()["role"] == "Analyst"

    # Charlie (Analyst) can create documents in Org A
    charlie_doc_create = await client.post(
        f"/api/v1/organizations/{org_a_id}/documents",
        json={
            "title": "Analyst Sheet",
            "filename": "sheet.pdf",
            "file_size_bytes": 1024,
            "mime_type": "application/pdf",
        },
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert charlie_doc_create.status_code == 201
    charlie_doc_id = charlie_doc_create.json()["id"]

    # Charlie (Analyst) CANNOT add other members (Admin only -> 403 Forbidden)
    analyst_add_mem = await client.post(
        f"/api/v1/organizations/{org_a_id}/members",
        json={"email": "bob@beta-capital.com", "role": "Analyst"},
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert analyst_add_mem.status_code == 403

    # Charlie (Analyst) CANNOT delete documents in Org A (Admin only -> 403 Forbidden)
    analyst_del_res = await client.delete(
        f"/api/v1/organizations/{org_a_id}/documents/{charlie_doc_id}",
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert analyst_del_res.status_code == 403

    # User A (Admin) CAN delete the document
    admin_del_res = await client.delete(
        f"/api/v1/organizations/{org_a_id}/documents/{charlie_doc_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert admin_del_res.status_code == 200

    # 10. Register User D as Reviewer
    res_d = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "diana@alpha-holdings.com",
            "password": "Password123!",
            "full_name": "Diana Reviewer",
        },
    )
    token_d = res_d.json()["access_token"]

    # User A adds Diana as Reviewer in Org A
    await client.post(
        f"/api/v1/organizations/{org_a_id}/members",
        json={"email": "diana@alpha-holdings.com", "role": "Reviewer"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Diana (Reviewer) CANNOT create documents (requires Admin or Analyst -> 403)
    reviewer_create_doc = await client.post(
        f"/api/v1/organizations/{org_a_id}/documents",
        json={
            "title": "Reviewer Attempt",
            "filename": "rev.pdf",
            "file_size_bytes": 1024,
            "mime_type": "application/pdf",
        },
        headers={"Authorization": f"Bearer {token_d}"},
    )
    assert reviewer_create_doc.status_code == 403
