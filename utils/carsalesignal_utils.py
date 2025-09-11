# listing_parser.py

import datetime
from bs4 import BeautifulSoup

def extract_make_model_year(mmy_div, title_text):
    def get_text_or_none(soup_element, default=None):
        """Helper function to get text or return default if element is None."""
        return soup_element.text.strip().lower() if soup_element else default

    # Check if mmy_div contains the year
    year = get_text_or_none(mmy_div.find('span', class_='valu year'))

    # Check if the span contains the make and model (inside 'makemodel' class)
    makemodel = get_text_or_none(mmy_div.find('a'))
    make = None  # default None
    model = None  # default None
    if makemodel:
        make_model_parts = makemodel.split(' ', 1)
        if len(make_model_parts) > 0:
            make = make_model_parts[0]  # First word is the make
            if len(make_model_parts) > 1:
                model = make_model_parts[1]  # Remaining part is the model
    # Fallback to using the title if year, make, and model are not found
    if not year or not make or not model:
        if title_text != "not found":  # if no title then we just can't parse it now can we?
            parts = title_text.split(' ')
            if year is None and parts[0].isdigit():  # only update if missing and digit
                year = parts[0]

            if make is None and parts[0].isdigit():  # only update if missing, could have year as 1st word
                make = parts[1] if len(parts) > 1 else 'not found'
            elif make is None:  # only update if missing, don't have year as 1st word
                make = parts[0] if len(parts) > 0 else 'not found'
            if model is None and parts[0].isdigit():  # only update if missing
                model = ' '.join(parts[2:]) if len(parts) > 2 else 'not found'  # year as 1st word make as 2nd word
            elif model is None:  # only update if missing
                model = ' '.join(parts[1:]) if len(parts) > 1 else 'not found'  # model as 1st word

    return {'year': year or 'not found', 'make': make or 'not found', 'model': model or 'not found'}


# Big, suggests craigslist parsing should be it's own library of python functions
def extract_listing_info(soup, url, area, updated):
    def get_text_or_default(soup_element, default="not found"):
        """Helper function to get text or return default if element is None."""
        return soup_element.text.strip().lower() if soup_element else default

    # Extract Title
    title = get_text_or_default(soup.find('span', id='titletextonly'))
    # Extract Price
    price = get_text_or_default(soup.find('span', class_='price'))
    # Extract Location (several Craigslist variants)
    location = "not found"
    # 1) Usually in small next to the title
    small_loc = soup.select_one(".postingtitletext small")
    if small_loc:
        location = small_loc.get_text(" ", strip=True).strip("() ").strip()

    # 2) Older pages show a mapaddress block
    if location == "not found":
        mapaddr = soup.select_one(".mapaddress")
        if mapaddr:
            location = mapaddr.get_text(strip=True)

    # 3) Some pages embed an address/title on the #map element
    if location == "not found":
        map_div = soup.select_one("#map")
        if map_div:
            # Some CL templates include data-address or put text in title
            location = (map_div.get("data-address") or map_div.get("title") or "not found").strip()


    # Extract Year, Make, and Model with helper function
    mmy_div = soup.find('div', class_='attr important')  # <div class="attr important">
    make_model_year = extract_make_model_year(mmy_div, title)
    year = make_model_year['year'].strip().lower()
    make = make_model_year['make'].strip().lower()
    model = make_model_year['model'].strip().lower()

    # Extract VIN
    vin = get_text_or_default(
        soup.find('div', class_='attr auto_vin').find('span', class_='valu')
        if soup.find('div', class_='attr auto_vin')
        else None
    )
    # Extract Condition
    condition = get_text_or_default(
        soup.find('div', class_='attr condition').find('a')
        if soup.find('div', class_='attr condition')
        else None
    )
    # Extract Cylinders
    cylinders = get_text_or_default(
        soup.find('div', class_='attr auto_cylinders').find('a')
        if soup.find('div', class_='attr auto_cylinders')
        else None
    )
    # Extract Drive
    drive = get_text_or_default(
        soup.find('div', class_='attr auto_drivetrain').find('a')
        if soup.find('div', class_='attr auto_drivetrain')
        else None
    )
    # Extract Fuel Type
    fuel = get_text_or_default(
        soup.find('div', class_='attr auto_fuel_type').find('a')
        if soup.find('div', class_='attr auto_fuel_type')
        else None
    )
    # Extract Odometer
    odometer = get_text_or_default(
        soup.find('div', class_='attr auto_miles').find('span', class_='valu')
        if soup.find('div', class_='attr auto_miles')
        else None
    )
    # Extract Paint Color
    paint_color = get_text_or_default(
        soup.find('div', class_='attr auto_paint').find('a')
        if soup.find('div', class_='attr auto_paint')
        else None
    )
    # Extract Title Status
    title_status = get_text_or_default(
        soup.find('div', class_='attr auto_title_status').find('a')
        if soup.find('div', class_='attr auto_title_status')
        else None
    )

    # Extract Transmission
    transmission = get_text_or_default(
        soup.find('div', class_='attr auto_transmission').find('a')
        if soup.find('div', class_='attr auto_transmission')
        else None
    )
    # Extract Vehicle Type
    vehicle_type = get_text_or_default(
        soup.find('div', class_='attr auto_bodytype').find('a')
        if soup.find('div', class_='attr auto_bodytype')
        else None
    )
    # Extract Delivery Availability (if present)
    delivery_available = "yes" if soup.find('div', class_='attr crypto_currency_ok') else "no"
    # Extract Posting Body
    posting_body = get_text_or_default(soup.find('section', id='postingbody'))
        
    # Extract Google Map Link
    google_map_link = "not found"
    map_div = soup.select_one("#map")
    if map_div:
        lat = map_div.get("data-latitude")
        lon = map_div.get("data-longitude")
        if lat and lon:
            google_map_link = f"https://www.google.com/maps?q={lat},{lon}"
    # Fallback: any visible Google Maps link on page
    if google_map_link == "not found":
        gm_a = soup.select_one("a[href*='google.com/maps'], a[href*='maps.app.goo.gl'], a[href*='maps.google']")
        if gm_a and gm_a.has_attr("href"):
            google_map_link = gm_a["href"]
            
    # Constructing the full result
    result = {
        "title": title,
        "year": year,
        "make": make,
        "model": model,
        "price": price,
        "location": location,
        "google_map_link": google_map_link,
        "condition": condition,
        "cylinders": cylinders,
        "drive": drive,
        "fuel": fuel,
        "odometer": odometer,
        "paint_color": paint_color,
        "title_status": title_status,
        "transmission": transmission,
        "vehicle_type": vehicle_type,
        "vin": vin,
        "delivery_available": delivery_available,
        "posting_body": posting_body.strip(),
        "url": url,
        "activity": "active",
        "added": str(datetime.datetime.now().isoformat()),
        "listing_soup": str(soup),
        "area": area,
        "updated": updated
    }
    return result

