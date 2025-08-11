# utils/db_utils.py

import logging
from psycopg2 import pool
from utils.email_utils import handle_error  # assumes send_mail and handle_error live here

# PostgreSQL connection pool setup for Tailscale-accessed desktop Postgres
postgres_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=20,
    user="ec2_writer",
    password="somethingsecure",
    host="100.80.9.95",  # desktop-1bt143s Tailscale IP
    port="5432",
    database="DVc4_data"
)

# Optional: Log and check initial connection
try:
    conn = postgres_pool.getconn()
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    result = cur.fetchone()
    print("Connected successfully:", result)
    cur.close()
    postgres_pool.putconn(conn)
except Exception as e:
    logging.error(f"Initial PostgreSQL connection failed: {e}")


def fetch_existing_listings_from_rds(area):
    conn = None
    cursor = None
    listings = {}
    try:
        conn = postgres_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT url
            FROM listings
            WHERE area = %s
            AND activity = 'active';
        """, (area,))
        for row in cursor.fetchall():
            listings[row[0]] = {'url': row[0]}
        logging.info(f"Fetched {len(listings)} listings from RDS for area {area}.")
    except Exception as e:
        logging.error(f"Error fetching listings for area {area}: {str(e)}")
        handle_error('fetch_existing_listings_from_rds', str(e), area)
    finally:
        if cursor:
            cursor.close()
        if conn:
            postgres_pool.putconn(conn)
        else:
            logging.error(f"Error in putconn for area {area}")
            handle_error('fetch_existing_listings_from_rds', f"putconn error for area {area}", area)
    return listings


def insert_listing_to_rds(listing):
    conn = None
    cursor = None
    try:
        conn = postgres_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO listings (
                year, make, model, area, url, title, price, location,
                google_map_link, posting_body, activity, updated, added, listing_soup,
                condition, cylinders, drive, fuel, odometer, paint_color, title_status,
                transmission, vehicle_type, vin, delivery_available
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            listing.get('year'), listing.get('make'), listing.get('model'), listing.get('area'), listing.get('url'),
            listing.get('title'), listing.get('price'), listing.get('location'), listing.get('google_map_link'),
            listing.get('posting_body'), listing.get('activity'), listing.get('updated'), listing.get('added'),
            listing.get('listing_soup'), listing.get('condition'), listing.get('cylinders'), listing.get('drive'),
            listing.get('fuel'), listing.get('odometer'), listing.get('paint_color'), listing.get('title_status'),
            listing.get('transmission'), listing.get('vehicle_type'), listing.get('vin'), listing.get('delivery_available')
        ))
        conn.commit()
        logging.info(f"Inserted listing: {listing['price']} {listing['title']} {listing['url']}")
    except Exception as e:
        logging.error(f"Error inserting listing {listing['url']}: {str(e)}")
        handle_error('insert_listing_to_rds', str(e), listing['area'], listing['url'])
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            postgres_pool.putconn(conn)


def update_listing_in_rds(url, activity, updated):
    conn = None
    cursor = None
    try:
        conn = postgres_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE listings
            SET activity = %s, updated = %s
            WHERE url = %s;
        """, (activity, updated, url))
        conn.commit()
        logging.info(f"Updated listing: {activity} {updated} {url}")
    except Exception as e:
        logging.error(f"Error updating listing {url}: {str(e)}")
        # duplicate erroring handle_error('update_listing_in_rds', str(e), '?', url)
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            postgres_pool.putconn(conn)
