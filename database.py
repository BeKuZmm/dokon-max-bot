import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from typing import Optional, List, Dict
import asyncio
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def connect(self):
        loop = asyncio.get_event_loop()
        self.pool = await loop.run_in_executor(
            None,
            lambda: ThreadedConnectionPool(1, 10, self.database_url, sslmode='require')
        )
        await self.create_tables()
        logger.info("✅ Ma'lumotlar bazasi ulandi")

    def _get_conn(self):
        return self.pool.getconn()

    def _put_conn(self, conn):
        self.pool.putconn(conn)

    async def _execute(self, query: str, params=None):
        loop = asyncio.get_event_loop()

        def _run():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                self._put_conn(conn)

        await loop.run_in_executor(None, _run)

    async def _fetchone(self, query: str, params=None) -> Optional[Dict]:
        loop = asyncio.get_event_loop()

        def _run():
            conn = self._get_conn()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, params)
                    return cur.fetchone()
            finally:
                self._put_conn(conn)

        result = await loop.run_in_executor(None, _run)
        return dict(result) if result else None

    async def _fetchall(self, query: str, params=None) -> List[Dict]:
        loop = asyncio.get_event_loop()

        def _run():
            conn = self._get_conn()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
            finally:
                self._put_conn(conn)

        results = await loop.run_in_executor(None, _run)
        return [dict(r) for r in results]

    async def _fetchval(self, query: str, params=None):
        loop = asyncio.get_event_loop()

        def _run():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    row = cur.fetchone()
                    return row[0] if row else None
            finally:
                self._put_conn(conn)

        return await loop.run_in_executor(None, _run)

    async def create_tables(self):
        await self._execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                full_name TEXT NOT NULL,
                username TEXT,
                phone TEXT,
                total_debt BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price BIGINT NOT NULL,
                photo_id TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                total_amount BIGINT NOT NULL,
                paid_amount BIGINT DEFAULT 0,
                debt_amount BIGINT DEFAULT 0,
                status TEXT DEFAULT 'confirmed',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                product_id INTEGER REFERENCES products(id),
                product_name TEXT NOT NULL,
                price BIGINT NOT NULL,
                quantity INTEGER DEFAULT 1
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, product_id)
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                amount BIGINT NOT NULL,
                confirmed BOOLEAN DEFAULT FALSE,
                rejected BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    # --- USER ---
    async def get_user(self, user_id: int) -> Optional[Dict]:
        return await self._fetchone("SELECT * FROM users WHERE id = %s", (user_id,))

    async def create_user(self, user_id: int, full_name: str, username: str = None):
        await self._execute(
            "INSERT INTO users (id, full_name, username) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (user_id, full_name, username)
        )

    async def update_user_phone(self, user_id: int, phone: str):
        await self._execute("UPDATE users SET phone = %s WHERE id = %s", (phone, user_id))

    async def get_all_users(self) -> List[Dict]:
        return await self._fetchall("SELECT * FROM users ORDER BY created_at DESC")

    async def get_all_debtors(self) -> List[Dict]:
        return await self._fetchall(
            "SELECT * FROM users WHERE total_debt > 0 ORDER BY total_debt DESC"
        )

    async def get_user_debt(self, user_id: int) -> Optional[Dict]:
        return await self._fetchone("SELECT total_debt FROM users WHERE id = %s", (user_id,))

    async def add_debt(self, user_id: int, amount: int):
        await self._execute(
            "UPDATE users SET total_debt = total_debt + %s WHERE id = %s",
            (amount, user_id)
        )

    # --- PRODUCTS ---
    async def get_all_products(self) -> List[Dict]:
        return await self._fetchall(
            "SELECT * FROM products WHERE is_active = TRUE ORDER BY created_at DESC"
        )

    async def add_product(self, name: str, price: int, photo_id: str = None):
        await self._execute(
            "INSERT INTO products (name, price, photo_id) VALUES (%s, %s, %s)",
            (name, price, photo_id)
        )

    async def delete_product(self, product_id: int):
        await self._execute(
            "UPDATE products SET is_active = FALSE WHERE id = %s", (product_id,)
        )

    async def get_product(self, product_id: int) -> Optional[Dict]:
        return await self._fetchone("SELECT * FROM products WHERE id = %s", (product_id,))

    # --- CART ---
    async def get_cart(self, user_id: int) -> List[Dict]:
        return await self._fetchall("""
            SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.photo_id
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))

    async def add_to_cart(self, user_id: int, product_id: int):
        await self._execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (%s, %s, 1)
            ON CONFLICT (user_id, product_id)
            DO UPDATE SET quantity = cart.quantity + 1
        """, (user_id, product_id))

    async def clear_cart(self, user_id: int):
        await self._execute("DELETE FROM cart WHERE user_id = %s", (user_id,))

    # --- ORDERS ---
    async def create_order(self, user_id: int, cart_items: List[Dict],
                           total_amount: int, paid_amount: int, debt_amount: int) -> int:
        loop = asyncio.get_event_loop()

        def _run():
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO orders (user_id, total_amount, paid_amount, debt_amount)
                        VALUES (%s, %s, %s, %s) RETURNING id
                    """, (user_id, total_amount, paid_amount, debt_amount))
                    order_id = cur.fetchone()[0]

                    for item in cart_items:
                        cur.execute("""
                            INSERT INTO order_items (order_id, product_id, product_name, price, quantity)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (order_id, item['product_id'], item['name'], item['price'], item['quantity']))

                    if debt_amount > 0:
                        cur.execute(
                            "UPDATE users SET total_debt = total_debt + %s WHERE id = %s",
                            (debt_amount, user_id)
                        )

                conn.commit()
                return order_id
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                self._put_conn(conn)

        return await loop.run_in_executor(None, _run)

    async def get_user_orders(self, user_id: int) -> List[Dict]:
        return await self._fetchall(
            "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        )

    # --- PAYMENTS ---
    async def create_payment(self, user_id: int, amount: int) -> int:
        return await self._fetchval(
            "INSERT INTO payments (user_id, amount) VALUES (%s, %s) RETURNING id",
            (user_id, amount)
        )

    async def get_payment(self, payment_id: int) -> Optional[Dict]:
        return await self._fetchone("SELECT * FROM payments WHERE id = %s", (payment_id,))

    async def confirm_payment(self, payment_id: int):
        loop = asyncio.get_event_loop()

        def _run():
            conn = self._get_conn()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
                    payment = cur.fetchone()
                    if payment and not payment['confirmed']:
                        cur.execute(
                            "UPDATE payments SET confirmed = TRUE WHERE id = %s", (payment_id,)
                        )
                        cur.execute(
                            "UPDATE users SET total_debt = GREATEST(0, total_debt - %s) WHERE id = %s",
                            (payment['amount'], payment['user_id'])
                        )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                self._put_conn(conn)

        await loop.run_in_executor(None, _run)

    async def reject_payment(self, payment_id: int):
        await self._execute(
            "UPDATE payments SET rejected = TRUE WHERE id = %s", (payment_id,)
        )

    async def get_pending_payments(self) -> List[Dict]:
        return await self._fetchall("""
            SELECT p.*, u.full_name FROM payments p
            JOIN users u ON p.user_id = u.id
            WHERE p.confirmed = FALSE AND p.rejected = FALSE
            ORDER BY p.created_at DESC
        """)

    async def get_user_payments(self, user_id: int) -> List[Dict]:
        return await self._fetchall(
            "SELECT * FROM payments WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
            (user_id,)
        )
