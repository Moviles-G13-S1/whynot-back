#!/usr/bin/env python3

"""
WhyNot local backend runner.

Run this file directly with the Play button in VS Code.

It automatically:

1. Starts Firebase Auth, Firestore, and Functions emulators.
2. Clears previous LOCAL emulator data.
3. Seeds canonical categories.
4. Seeds the city catalog.
5. Seeds Bogotá stores.
6. Creates one local administrator.
7. Creates four regular demo users.
8. Creates all eight wishlist categories for every regular user.
9. Creates two unique products per wishlist.
10. Keeps the Firebase Emulator Suite running.

IMPORTANT:
This file is LOCAL ONLY.

It is intentionally locked to the `demo-whynot` Firebase project and must
never be pointed at the production WhyNot project.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


# ===========================================================================
# LOCAL FIREBASE CONFIGURATION
# ===========================================================================

REPO_ROOT = Path(__file__).resolve().parent

PROJECT_ID = "demo-whynot"

HOST = "127.0.0.1"

AUTH_PORT = 9099
FIRESTORE_PORT = 8080
FUNCTIONS_PORT = 5001

# Every account in the local emulator uses the same password.
DEMO_PASSWORD = "123456789"


# ===========================================================================
# ADMIN ACCOUNT
# ===========================================================================

# The administrator exists in Firebase Authentication and receives the
# `admin: true` custom claim.
#
# It intentionally does NOT receive a Firestore `users` document so the
# Smart Recommendation algorithm does not consider the admin as a candidate.
ADMIN_USER = {
    "uid": "admin-user",
    "name": "Admin",
    "email": "admin@gmail.com",
}


# ===========================================================================
# REGULAR DEMO USERS
# ===========================================================================
#
# Smart Recommendation pairs:
#
# Juliana <-> Emma
# Mateo   <-> Santiago
#
# The women are in the same age group and the men are in the same age group.
# Their preferred categories are intentionally different so the recommendation
# feature still has meaningful products to suggest.
# ===========================================================================

TEST_USERS = [
    {
        "uid": "user-juliana",
        "name": "Juliana",
        "email": "Juliana@gmail.com",
        "gender": "Female",
        "age": 22,
        "preferredCategoryId": "fashion",
        "cityId": "bogota",
    },
    {
        "uid": "user-emma",
        "name": "Emma",
        "email": "Emma@gmail.com",
        "gender": "Female",
        "age": 23,
        "preferredCategoryId": "beauty",
        "cityId": "medellin",
    },
    {
        "uid": "user-mateo",
        "name": "Mateo",
        "email": "Mateo@gmail.com",
        "gender": "Male",
        "age": 22,
        "preferredCategoryId": "technology",
        "cityId": "cali",
    },
    {
        "uid": "user-santiago",
        "name": "Santiago",
        "email": "Santiago@gmail.com",
        "gender": "Male",
        "age": 23,
        "preferredCategoryId": "home",
        "cityId": "bogota",
    },
]


# ===========================================================================
# WHYNOT CATEGORIES
# ===========================================================================

CATEGORIES = {
    "fashion": "Fashion",
    "beauty": "Beauty",
    "technology": "Technology",
    "home": "Home",
    "accessories": "Accessories",
    "travel": "Travel",
    "gifts": "Gifts",
    "other": "Other",
}


# ===========================================================================
# DEMO PRODUCT CATALOG
# ===========================================================================
#
# Each category contains exactly eight products.
#
# User 0 receives products 0-1.
# User 1 receives products 2-3.
# User 2 receives products 4-5.
# User 3 receives products 6-7.
#
# Therefore every product belongs to exactly one user.
#
# 4 users
# x 8 wishlists
# x 2 products
# = 64 unique products.
# ===========================================================================

PRODUCT_CATALOG = {
    "fashion": [
        ("Linen Blazer", "Mango", 289900),
        ("Satin Midi Skirt", "ZARA", 199900),
        ("Black Leather Jacket", "Massimo Dutti", 699900),
        ("Wide Leg Jeans", "Levi's", 329900),
        ("Relaxed Overshirt", "Pull&Bear", 249900),
        ("Straight Chinos", "Uniqlo", 189900),
        ("Knit Polo", "COS", 279900),
        ("Classic Denim Jacket", "Calvin Klein", 459900),
    ],

    "beauty": [
        ("Lip Glow Balm", "Dior", 189000),
        ("Soft Pinch Blush", "Rare Beauty", 145000),
        ("Libre Eau de Parfum", "YSL Beauty", 599000),
        ("Hydrating Face Cream", "Clinique", 229000),
        ("Matte Lipstick", "MAC", 119000),
        ("Daily Cleanser", "CeraVe", 79000),
        ("Vitamin C Serum", "La Roche-Posay", 169000),
        ("Perfume Mist", "Sol de Janeiro", 179000),
    ],

    "technology": [
        ("Wireless Headphones", "Sony", 799900),
        ("Smart Watch", "Samsung", 1099900),
        ("Mechanical Keyboard", "Logitech", 459900),
        ("Portable SSD", "SanDisk", 399900),
        ("Bluetooth Speaker", "JBL", 349900),
        ("Wireless Mouse", "Logitech", 229900),
        ("Tablet", "Lenovo", 1299900),
        ("Noise Cancelling Earbuds", "Bose", 999900),
    ],

    "home": [
        ("Table Lamp", "IKEA", 179900),
        ("Cotton Bedding Set", "Zara Home", 399900),
        ("Ceramic Vase", "Homecenter", 89900),
        ("Scented Candle", "Bath & Body Works", 129900),
        ("Coffee Table", "IKEA", 799900),
        ("Throw Blanket", "Zara Home", 249900),
        ("Desk Organizer", "Muji", 119900),
        ("Floor Lamp", "Homecenter", 319900),
    ],

    "accessories": [
        ("Gold Hoop Earrings", "TOUS", 499900),
        ("Mini Shoulder Bag", "Coach", 1299900),
        ("Silver Bracelet", "Pandora", 389900),
        ("Classic Sunglasses", "Ray-Ban", 699900),
        ("Leather Wallet", "Fossil", 399900),
        ("Canvas Backpack", "Herschel", 359900),
        ("Minimalist Watch", "Daniel Wellington", 799900),
        ("Crossbody Bag", "Longchamp", 1099900),
    ],

    "travel": [
        ("Cabin Suitcase", "Samsonite", 899900),
        ("Packing Cube Set", "Roncato", 169900),
        ("Travel Backpack", "Osprey", 699900),
        ("Neck Pillow", "Cabeau", 199900),
        ("Passport Wallet", "Bellroy", 389900),
        ("Travel Adapter", "Anker", 179900),
        ("Weekend Duffel", "Tumi", 1499900),
        ("Luggage Organizer", "Samsonite", 219900),
    ],

    "gifts": [
        ("Mini Building Set", "LEGO", 129900),
        ("Instant Camera", "Fujifilm", 599900),
        ("Plush Bear", "Miniso", 69900),
        ("Premium Notebook", "Moleskine", 149900),
        ("Board Game", "Catan", 219900),
        ("Chocolate Gift Box", "Lindt", 99900),
        ("Photo Album", "Miniso", 59900),
        ("Portable Photo Printer", "Canon", 549900),
    ],

    "other": [
        ("Yoga Mat", "Nike", 189900),
        ("Reusable Bottle", "Stanley", 249900),
        ("Running Shoes", "Adidas", 599900),
        ("Tennis Racket", "Wilson", 799900),
        ("Sketchbook", "Moleskine", 119900),
        ("Desk Calculator", "Casio", 89900),
        ("Reading Light", "Xiaomi", 149900),
        ("Gym Bag", "Under Armour", 299900),
    ],
}


# ===========================================================================
# SAFETY
# ===========================================================================

def ensure_local_project() -> None:
    """Prevent the runner from ever targeting production."""

    if not PROJECT_ID.startswith("demo-"):
        raise RuntimeError(
            "REFUSING TO RUN.\n"
            "Local development must use a demo-* Firebase project."
        )


# ===========================================================================
# DEPENDENCY SETUP
# ===========================================================================

def ensure_node_dependencies() -> None:
    """Install root Node dependencies when node_modules is missing."""

    node_modules = REPO_ROOT / "node_modules"

    if node_modules.exists():
        return

    print("\nInstalling Node dependencies...\n")

    subprocess.run(
        ["npm", "ci"],
        cwd=REPO_ROOT,
        check=True,
    )


def find_python_313() -> str:
    """Find the Python runtime expected by the current Firebase configuration."""

    python_command = shutil.which("python3.13")

    if python_command is None:
        raise RuntimeError(
            "\nPython 3.13 was not found.\n\n"
            "The current WhyNot Firebase Functions runtime is python313.\n"
            "Install Python 3.13 and press Play again."
        )

    return python_command

def ensure_functions_python() -> None:
    """
    Create, activate, and repair the Firebase Functions virtual environment.

    The local backend runner always executes inside functions/venv.

    This lets any team member press Play without manually activating the
    virtual environment or installing Python dependencies.
    """

    venv_directory = (
        REPO_ROOT
        / "functions"
        / "venv"
    )

    if os.name == "nt":
        venv_python = (
            venv_directory
            / "Scripts"
            / "python.exe"
        )
    else:
        venv_python = (
            venv_directory
            / "bin"
            / "python"
        )

    # ---------------------------------------------------------------
    # Create the virtual environment when it does not exist.
    # ---------------------------------------------------------------

    if not venv_python.exists():
        python_command = find_python_313()

        print(
            "\nCreating Firebase Functions virtual environment...\n"
        )

        subprocess.run(
            [
                python_command,
                "-m",
                "venv",
                str(venv_directory),
            ],
            check=True,
        )

    # ---------------------------------------------------------------
    # Detect whether THIS process is actually running inside the venv.
    #
    # Do not compare resolved Python executable paths here.
    # On macOS, venv/bin/python may be a symlink to the system Python
    # executable, which would make both paths appear identical.
    #
    # sys.prefix correctly identifies the active virtual environment.
    # ---------------------------------------------------------------

    running_inside_venv = (
        Path(sys.prefix).resolve()
        == venv_directory.resolve()
    )

    if not running_inside_venv:
        print(
            "\nRestarting runner inside functions/venv...\n"
        )

        os.execv(
            str(venv_python),
            [
                str(venv_python),
                str(Path(__file__).resolve()),
            ],
        )

    # ---------------------------------------------------------------
    # At this point the current Python process is guaranteed to be
    # running from functions/venv.
    # ---------------------------------------------------------------

    print(
        "\nChecking Firebase Functions Python dependencies...\n"
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(
                REPO_ROOT
                / "functions"
                / "requirements.txt"
            ),
        ],
        check=True,
    )

    # ---------------------------------------------------------------
    # The local seed runner also needs Firebase Admin SDK.
    #
    # The current Functions requirements file only declares
    # firebase_functions, so make sure firebase_admin is available for
    # the local data seeder as well.
    # ---------------------------------------------------------------

    try:
        import firebase_admin  # noqa: F401

        print(
            "Firebase Admin SDK is available."
        )

    except ModuleNotFoundError:
        print(
            "\nInstalling Firebase Admin SDK for local seeding...\n"
        )

        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "firebase-admin",
            ],
            check=True,
        )

        # Verify immediately using the SAME interpreter running this file.
        import firebase_admin  # noqa: F401

        print(
            "Firebase Admin SDK installed successfully."
        )
# ===========================================================================
# EMULATOR HELPERS
# ===========================================================================

def port_is_open(port: int) -> bool:
    """Return True when localhost is already listening on the given port."""

    try:
        with socket.create_connection(
            (HOST, port),
            timeout=0.3,
        ):
            return True
    except OSError:
        return False


def ensure_ports_are_free() -> None:
    """Prevent accidentally starting two Emulator Suite instances."""

    required_ports = [
        AUTH_PORT,
        FIRESTORE_PORT,
        FUNCTIONS_PORT,
    ]

    occupied = [
        port
        for port in required_ports
        if port_is_open(port)
    ]

    if occupied:
        raise RuntimeError(
            "\nFirebase Emulator ports are already in use:\n"
            f"{occupied}\n\n"
            "Stop the previous emulator process and press Play again."
        )


def wait_for_port(
    process: subprocess.Popen,
    port: int,
    timeout_seconds: int = 120,
) -> None:
    """Wait until one Firebase emulator starts listening."""

    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "Firebase Emulator Suite stopped before becoming ready."
            )

        if port_is_open(port):
            return

        time.sleep(0.5)

    raise TimeoutError(
        f"Timed out waiting for {HOST}:{port}."
    )


def start_emulators() -> subprocess.Popen:
    """Start Auth, Firestore, and Functions Emulator Suite services."""

    ensure_ports_are_free()

    environment = os.environ.copy()

    # Helps avoid the macOS Objective-C fork crash that can happen with the
    # local Python Cloud Functions worker.
    environment.setdefault(
        "OBJC_DISABLE_INITIALIZE_FORK_SAFETY",
        "YES",
    )

    command = [
        "npx",
        "firebase",
        "emulators:start",
        "--only",
        "auth,firestore,functions",
        "--project",
        PROJECT_ID,
    ]

    print(
        "\n"
        "============================================================\n"
        "STARTING WHYNOT LOCAL BACKEND\n"
        "============================================================\n"
    )

    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=environment,
    )

    wait_for_port(
        process,
        AUTH_PORT,
    )

    wait_for_port(
        process,
        FIRESTORE_PORT,
    )

    wait_for_port(
        process,
        FUNCTIONS_PORT,
    )

    print("\nFirebase emulators are ready.")

    return process


# ===========================================================================
# RESET LOCAL DATA
# ===========================================================================

def delete_url(url: str) -> None:
    """Perform a DELETE request against an Emulator Suite admin endpoint."""

    request = Request(
        url=url,
        method="DELETE",
    )

    with urlopen(
        request,
        timeout=15,
    ):
        pass


def reset_local_data() -> None:
    """
    Clear Authentication and Firestore.

    These endpoints belong to demo-whynot only. Production is never touched.
    """

    print("\nClearing previous local emulator data...")

    delete_url(
        "http://"
        f"{HOST}:{AUTH_PORT}"
        "/emulator/v1/projects/"
        f"{PROJECT_ID}/accounts"
    )

    delete_url(
        "http://"
        f"{HOST}:{FIRESTORE_PORT}"
        "/emulator/v1/projects/"
        f"{PROJECT_ID}"
        "/databases/(default)/documents"
    )

    print("Local data cleared.")


# ===========================================================================
# CANONICAL BACKEND SEEDS
# ===========================================================================

def run_firestore_seed(
    npm_script: str,
    label: str,
) -> None:
    """
    Run one existing repository seed against the Firestore emulator.

    Existing seed scripts remain the source of truth for categories, cities,
    and stores.
    """

    environment = os.environ.copy()

    environment[
        "FIRESTORE_EMULATOR_HOST"
    ] = f"{HOST}:{FIRESTORE_PORT}"

    print(f"\nSeeding {label}...")

    subprocess.run(
        [
            "npm",
            "run",
            npm_script,
            "--",
            "--project",
            PROJECT_ID,
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def seed_reference_data() -> None:
    """
    Populate collections maintained by existing backend scripts.

    Order matters because user profiles reference categories and cities.
    """

    run_firestore_seed(
        "seed:categories",
        "categories",
    )

    run_firestore_seed(
        "seed:cities",
        "cities",
    )

    run_firestore_seed(
        "seed:stores",
        "Bogotá stores",
    )


# ===========================================================================
# DEMO DATA HELPERS
# ===========================================================================

def slug(value: str) -> str:
    """Convert a string into a stable lowercase identifier."""

    return re.sub(
        r"[^a-z0-9]+",
        "-",
        value.lower(),
    ).strip("-")


def product_image_url(
    user_name: str,
    category_id: str,
    product_name: str,
) -> str:
    """
    Build a deterministic demo image URL.

    The URL is different for every product so cards have varied images.
    These images are demo placeholders and are not stored in Firebase Storage.
    """

    seed = slug(
        f"whynot-{user_name}-{category_id}-{product_name}"
    )

    return (
        "https://picsum.photos/"
        f"seed/{seed}/600/600"
    )


# ===========================================================================
# ADMIN
# ===========================================================================

def create_admin_user(
    auth_module,
    firebase_app,
) -> None:
    """
    Create the single local administrator.

    The account receives `admin: true` but no Firestore user profile.
    """

    print("\nCreating administrator account...")

    auth_module.create_user(
        uid=ADMIN_USER["uid"],
        email=ADMIN_USER["email"],
        password=DEMO_PASSWORD,
        display_name=ADMIN_USER["name"],
        app=firebase_app,
    )

    auth_module.set_custom_user_claims(
        ADMIN_USER["uid"],
        {
            "admin": True,
        },
        app=firebase_app,
    )

    print(
        f"  ✓ {ADMIN_USER['email']}"
    )


# ===========================================================================
# USERS / WISHLISTS / PRODUCTS
# ===========================================================================

def create_regular_users(
    auth_module,
    firebase_app,
    database,
) -> None:
    """
    Create all four demo users and all of their application data.
    """

    print("\nCreating regular users...")

    created_at = datetime.now(
        timezone.utc,
    )

    for user_index, user in enumerate(TEST_USERS):
        auth_module.create_user(
            uid=user["uid"],
            email=user["email"],
            password=DEMO_PASSWORD,
            display_name=user["name"],
            app=firebase_app,
        )

        database.collection(
            "users"
        ).document(
            user["uid"]
        ).set(
            {
                "name": user["name"],
                "email": user["email"],
                "gender": user["gender"],
                "age": user["age"],
                "preferredCategoryId": (
                    user["preferredCategoryId"]
                ),
                "cityId": user["cityId"],
                "createdAt": created_at,
                "updatedAt": created_at,
            }
        )

        create_user_wishlists_and_products(
            database=database,
            user=user,
            user_index=user_index,
            created_at=created_at,
        )

        print(
            "  ✓ "
            f"{user['email']} — "
            f"{user['gender']}, "
            f"{user['age']}, "
            f"{user['preferredCategoryId']}, "
            f"{user['cityId']}"
        )


def create_user_wishlists_and_products(
    *,
    database,
    user: dict,
    user_index: int,
    created_at: datetime,
) -> None:
    """
    Create eight wishlists and sixteen products for one user.

    Exactly one product per user is marked as purchased. It belongs to that
    user's preferred category, which gives Smart Recommendation a clear
    purchased candidate to prefer.

    The current backend contract requires `purchasedAt` on every product:
    - saved product  -> purchased == False, purchasedAt == None
    - bought product -> purchased == True, purchasedAt == timestamp
    """

    uid = user["uid"]

    for category_id in CATEGORIES:
        wishlist_id = (
            f"{uid}-{category_id}"
        )

        catalog = PRODUCT_CATALOG[
            category_id
        ]

        start = user_index * 2

        selected_products = catalog[
            start:start + 2
        ]

        wishlist_image = product_image_url(
            user["name"],
            category_id,
            selected_products[0][0],
        )

        database.collection(
            "wishlists"
        ).document(
            wishlist_id
        ).set(
            {
                "ownerId": uid,
                "categoryId": category_id,
                "imageUrl": wishlist_image,
                "createdAt": created_at,
                "updatedAt": created_at,
            }
        )

        for product_index, (
            product_name,
            brand,
            price,
        ) in enumerate(selected_products):

            product_id = (
                f"{uid}-"
                f"{category_id}-"
                f"{product_index + 1}"
            )

            purchased = (
                category_id
                == user["preferredCategoryId"]
                and product_index == 0
            )

            purchased_at = (
                created_at
                if purchased
                else None
            )

            database.collection(
                "products"
            ).document(
                product_id
            ).set(
                {
                    "ownerId": uid,
                    "wishlistId": wishlist_id,
                    "categoryId": category_id,
                    "name": product_name,
                    "brand": brand,
                    "price": price,
                    "imageUrl": product_image_url(
                        user["name"],
                        category_id,
                        product_name,
                    ),
                    "productUrl": (
                        "https://example.com/"
                        f"whynot/{product_id}"
                    ),
                    "purchased": purchased,
                    "purchasedAt": purchased_at,
                    "createdAt": created_at,
                    "updatedAt": created_at,
                }
            )


# ===========================================================================
# FIREBASE ADMIN SDK
# ===========================================================================

def seed_demo_data() -> None:
    """
    Connect Firebase Admin SDK exclusively to the local emulator and populate
    demo Authentication and Firestore data.
    """

    os.environ[
        "FIREBASE_AUTH_EMULATOR_HOST"
    ] = f"{HOST}:{AUTH_PORT}"

    os.environ[
        "FIRESTORE_EMULATOR_HOST"
    ] = f"{HOST}:{FIRESTORE_PORT}"

    # Imports intentionally happen after emulator environment variables have
    # been configured.
    from firebase_admin import (
        auth,
        firestore,
        initialize_app,
    )

    firebase_app = initialize_app(
        options={
            "projectId": PROJECT_ID,
        },
        name="whynot-local-seeder",
    )

    database = firestore.client(
        app=firebase_app,
    )

    create_admin_user(
        auth_module=auth,
        firebase_app=firebase_app,
    )

    create_regular_users(
        auth_module=auth,
        firebase_app=firebase_app,
        database=database,
    )


# ===========================================================================
# SUMMARY
# ===========================================================================

def print_summary() -> None:
    """Print useful local credentials after setup completes."""

    print(
        "\n"
        "============================================================\n"
        "WHYNOT LOCAL BACKEND READY\n"
        "============================================================"
    )

    print(
        "\nEmulator UI:\n"
        "  http://127.0.0.1:4000"
    )

    print(
        "\nPASSWORD FOR EVERY ACCOUNT:\n"
        f"  {DEMO_PASSWORD}"
    )

    print(
        "\nADMIN:\n"
        f"  {ADMIN_USER['email']}"
    )

    print("\nREGULAR USERS:")

    for user in TEST_USERS:
        print(
            "  "
            f"{user['email']:<24} "
            f"{user['gender']:<6} "
            f"age={user['age']:<2} "
            f"preferred={user['preferredCategoryId']:<10} "
            f"city={user['cityId']}"
        )

    print(
        "\nSMART FEATURE PAIRS:\n"
        "  Juliana ↔ Emma\n"
        "  Mateo   ↔ Santiago"
    )

    print(
        "\nLOCAL DATA CREATED:\n"
        "  1 admin Auth account\n"
        "  4 regular Auth accounts\n"
        "  4 Firestore user profiles\n"
        "  8 categories\n"
        "  25 cities\n"
        "  32 wishlists\n"
        "  64 unique products\n"
        "  4 purchased products\n"
        "  16 Bogotá stores\n"
    )

    print(
        "Press Ctrl+C to stop the local backend.\n"
        "============================================================\n"
    )


# ===========================================================================
# MAIN
# ===========================================================================

def main() -> None:
    """Run the complete local WhyNot backend with one click."""

    ensure_local_project()

    ensure_node_dependencies()

    ensure_functions_python()

    emulator_process = None

    try:
        emulator_process = start_emulators()

        reset_local_data()

        seed_reference_data()

        seed_demo_data()

        print_summary()

        # Keep this Python process alive while Emulator Suite is running.
        emulator_process.wait()

    except KeyboardInterrupt:
        print(
            "\nStopping WhyNot local backend..."
        )

    finally:
        if (
            emulator_process is not None
            and emulator_process.poll() is None
        ):
            try:
                emulator_process.send_signal(
                    signal.SIGINT
                )

                emulator_process.wait(
                    timeout=10,
                )

            except Exception:
                emulator_process.terminate()


if __name__ == "__main__":
    main()