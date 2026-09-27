import os
from datetime import datetime, timedelta, timezone

import psycopg
from jose import JWTError, jwt
from litestar import Litestar, Request, get, patch, post
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from passlib.context import CryptContext
from psycopg.rows import dict_row
from pydantic import BaseModel

DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54395/spectrum")
SECRET = os.environ.get("JWT_SECRET", "spectrum-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "calibrator": {"role": "writer", "password_hash": pwd.hash("calib123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id serial PRIMARY KEY,
    lamp text NOT NULL,
    nominal_nm double precision NOT NULL,
    measured_nm double precision NOT NULL,
    status text NOT NULL,
    verdict text NOT NULL DEFAULT '',
    reason text NOT NULL DEFAULT '',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL
);
"""

# 只读导出包：签发那一刻把灯种/标称/实测/结论/理由冻结进来，之后任务重判不再回写。
SCHEMA_PACKAGES = """
CREATE TABLE IF NOT EXISTS packages (
    id serial PRIMARY KEY,
    job_id integer NOT NULL UNIQUE REFERENCES jobs(id),
    lamp text NOT NULL,
    nominal_nm double precision NOT NULL,
    measured_nm double precision NOT NULL,
    verdict text NOT NULL,
    reason text NOT NULL,
    signed_by text NOT NULL,
    signed_at timestamptz NOT NULL
);
"""


def connect():
    return psycopg.connect(DSN, row_factory=dict_row)


class LoginIn(BaseModel):
    username: str
    password: str


class JobIn(BaseModel):
    lamp: str
    nominal_nm: float
    measured_nm: float


class JobPatchIn(BaseModel):
    measured_nm: float


def user_from_request(request: Request) -> dict:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = jwt.decode(auth[7:], SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="无效令牌") from exc
    if payload.get("sub") not in USERS:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="无效令牌")
    return {"username": payload["sub"], "role": payload.get("role")}


@get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "spectrum-wavelength-desk"}


@post("/api/login")
async def login(data: LoginIn) -> dict:
    u = USERS.get(data.username)
    if not u or not pwd.verify(data.password, u["password_hash"]):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    token = jwt.encode(
        {
            "sub": data.username,
            "role": u["role"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"access_token": token, "role": u["role"], "username": data.username}


@get("/api/jobs")
async def list_jobs(request: Request) -> list:
    user_from_request(request)
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, lamp, nominal_nm, measured_nm, status, verdict, reason, created_by FROM jobs ORDER BY id DESC"
        ).fetchall()
        return list(rows)


@get("/api/jobs/{job_id:int}")
async def get_job(request: Request, job_id: int) -> dict:
    user_from_request(request)
    with connect() as conn:
        row = conn.execute(
            "SELECT id, lamp, nominal_nm, measured_nm, status, verdict, reason, created_by FROM jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="任务不存在")
        return dict(row)


@post("/api/jobs")
async def create_job(request: Request, data: JobIn) -> dict:
    user = user_from_request(request)
    if user["role"] != "writer":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="仅校准员可提交")
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO jobs(lamp, nominal_nm, measured_nm, status, verdict, reason, created_by, created_at)
            VALUES (%s,%s,%s,'pending','','',%s,%s) RETURNING id
            """,
            (data.lamp.strip(), data.nominal_nm, data.measured_nm, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
        return {"id": row["id"], "status": "pending"}


@patch("/api/jobs/{job_id:int}")
async def update_job(request: Request, job_id: int, data: JobPatchIn) -> dict:
    user = user_from_request(request)
    if user["role"] != "writer":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="仅校准员可改实测")
    with connect() as conn:
        row = conn.execute(
            """
            UPDATE jobs SET measured_nm=%s, status='pending', verdict='', reason=''
            WHERE id=%s RETURNING id
            """,
            (data.measured_nm, job_id),
        ).fetchone()
        conn.commit()
        if not row:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"id": job_id, "status": "pending"}


@get("/api/packages")
async def list_packages(request: Request) -> list:
    user_from_request(request)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, job_id, lamp, nominal_nm, measured_nm, verdict, reason, signed_by, signed_at
            FROM packages ORDER BY id DESC
            """
        ).fetchall()
        return list(rows)


@get("/api/packages/{pkg_id:int}")
async def get_package(request: Request, pkg_id: int) -> dict:
    user_from_request(request)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, job_id, lamp, nominal_nm, measured_nm, verdict, reason, signed_by, signed_at
            FROM packages WHERE id = %s
            """,
            (pkg_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="导出包不存在")
        return dict(row)


@post("/api/jobs/{job_id:int}/sign")
async def sign_job(request: Request, job_id: int) -> dict:
    user = user_from_request(request)
    if user["role"] != "writer":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="仅校准员可签发")
    with connect() as conn:
        job = conn.execute(
            "SELECT id, lamp, nominal_nm, measured_nm, status, verdict, reason FROM jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        if job["status"] != "done":
            raise HTTPException(status_code=409, detail="未结案，不能签发")
        existing = conn.execute("SELECT id FROM packages WHERE job_id = %s", (job_id,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="该任务已签发")
        row = conn.execute(
            """
            INSERT INTO packages(job_id, lamp, nominal_nm, measured_nm, verdict, reason, signed_by, signed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """,
            (
                job["id"],
                job["lamp"],
                job["nominal_nm"],
                job["measured_nm"],
                job["verdict"],
                job["reason"],
                user["username"],
                datetime.now(timezone.utc),
            ),
        ).fetchone()
        conn.commit()
        return {"id": row["id"], "job_id": job_id, "status": "signed"}


def on_startup() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)
        conn.execute(SCHEMA_PACKAGES)
        n = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
        if n == 0:
            now = datetime.now(timezone.utc)
            conn.execute(
                """
                INSERT INTO jobs(lamp, nominal_nm, measured_nm, status, verdict, reason, created_by, created_at)
                VALUES
                ('氦灯-587', 587.56, 587.50, 'done', '合格', '偏差 0.0600 nm 在允差内', 'seed', %s),
                ('汞灯-546', 546.07, 546.30, 'done', '超差', '偏差 0.2300 nm 超过允差 0.08', 'seed', %s)
                """,
                (now, now),
            )
        conn.commit()


app = Litestar(
    route_handlers=[health, login, list_jobs, get_job, create_job, update_job, list_packages, get_package, sign_job],
    on_startup=[on_startup],
)
