"""
Real Estate Brokerage - Market Intelligence Raw Data Generator
Complexity: HIGH

Generates the raw data layer for the Crestline Realty Market Intelligence Platform.
Mirrors three source schemas:
  - raw_mls       (market-wide MLS feed, including competitor listings)
  - raw_crm       (Crestline-only Salesforce data)
  - raw_external  (Zillow, Freddie Mac PMMS, Census/BLS, Walk Score)

Scope:
  - 3 markets (Bay Area, SoCal, Pacific Northwest), 60 zip codes
  - 2023-01-01 to 2026-06-05 (about 3.4 years)
  - 23 tables, around 328,000 rows total

Run:
  python 04-real_estate_brokerage_market_intelligence_raw_data_high_data_generator-cn.py

Outputs:
  - data/01..23_*.tsv  (idempotent -- old files are deleted first)
  - real_estate_brokerage_market_intelligence_raw_data_high.sqlite

For design rationale and schema details, see the companion documents:
  - 01-real_estate_brokerage_market_intelligence_raw_data_high_business_context-cn.md
  - 02-real_estate_brokerage_market_intelligence_raw_data_high_er_document-cn.md
  - 03-real_estate_brokerage_market_intelligence_raw_data_high_sql_queries-cn.md
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl
from faker import Faker
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATASET_NAME = "real_estate_brokerage_market_intelligence_raw_data_high"
DATABASE_PATH = OUTPUT_DIR / f"{DATASET_NAME}.sqlite"

FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# Time range
DATA_START = date(2023, 1, 1)
DATA_END = date(2026, 6, 5)
CURRENT_DATE = date(2026, 6, 5)

# Row count targets
N_PROPERTIES = 25_000
N_LISTINGS = 40_000
N_EVENT_HISTORY = 65_000
N_SOLD = 25_000          # Natural result of a ~62% sell-through rate
N_PENDING = 800
N_SHOWINGS = 75_000      # Upper bound target; the 2.5/1.5/0.6 density yields ~60-65K naturally
N_OFFICES = 8
N_AGENTS = 200
N_CONTACTS = 5_000
N_OPPORTUNITIES = 10_000
N_CRM_TRANSACTIONS = 2_500
N_AGENT_ACTIVITIES = 50_000

# MLS-CRM coupling: ~30% of listings are tagged as Crestline,
# and within those, ~5% use a spelling variant (forcing downstream fuzzy matching).
CRESTLINE_BROKERAGE_SHARE = 0.30
CRESTLINE_BROKERAGE_VARIANTS = [
    ("Crestline Realty", 0.95),
    ("Crestline Realty Inc", 0.015),
    ("Crestline Realty LLC", 0.015),
    ("CRESTLINE REALTY", 0.010),
    ("Crestline  Realty", 0.010),  # double space
]
COMPETITOR_BROKERAGES = [
    "Compass", "Coldwell Banker", "Sotheby's International",
    "Keller Williams", "Berkshire Hathaway HomeServices",
    "Redfin", "Side Inc", "RE/MAX",
]

# ============================================================================
# Reference data -- 3 markets, 12 counties, 30 cities, 60 zips
# ============================================================================

MARKETS = [
    {"market_id": 1, "market_code": "BAY", "market_name": "Bay Area", "state": "CA",
     "median_price": 1_200_000, "price_std": 350_000},
    {"market_id": 2, "market_code": "SOCAL", "market_name": "Southern California", "state": "CA",
     "median_price": 900_000, "price_std": 280_000},
    {"market_id": 3, "market_code": "PNW", "market_name": "Pacific Northwest", "state": "WA",
     "median_price": 700_000, "price_std": 220_000},
]

COUNTIES = [
    # Bay Area
    {"county_id": 1, "county_name": "San Francisco", "state": "CA", "market_id": 1},
    {"county_id": 2, "county_name": "San Mateo", "state": "CA", "market_id": 1},
    {"county_id": 3, "county_name": "Santa Clara", "state": "CA", "market_id": 1},
    {"county_id": 4, "county_name": "Alameda", "state": "CA", "market_id": 1},
    # SoCal
    {"county_id": 5, "county_name": "Los Angeles", "state": "CA", "market_id": 2},
    {"county_id": 6, "county_name": "Orange", "state": "CA", "market_id": 2},
    {"county_id": 7, "county_name": "San Diego", "state": "CA", "market_id": 2},
    # PNW
    {"county_id": 8, "county_name": "King", "state": "WA", "market_id": 3},
    {"county_id": 9, "county_name": "Pierce", "state": "WA", "market_id": 3},
    {"county_id": 10, "county_name": "Snohomish", "state": "WA", "market_id": 3},
    {"county_id": 11, "county_name": "Kitsap", "state": "WA", "market_id": 3},
    {"county_id": 12, "county_name": "Ventura", "state": "CA", "market_id": 2},
]

CITIES = [
    # Bay Area / San Francisco County
    {"city_id": 1, "city_name": "San Francisco", "county_id": 1},
    # Bay Area / San Mateo County
    {"city_id": 2, "city_name": "Daly City", "county_id": 2},
    {"city_id": 3, "city_name": "Redwood City", "county_id": 2},
    {"city_id": 4, "city_name": "Burlingame", "county_id": 2},
    # Bay Area / Santa Clara County
    {"city_id": 5, "city_name": "Palo Alto", "county_id": 3},
    {"city_id": 6, "city_name": "San Jose", "county_id": 3},
    {"city_id": 7, "city_name": "Mountain View", "county_id": 3},
    {"city_id": 8, "city_name": "Sunnyvale", "county_id": 3},
    # Bay Area / Alameda County
    {"city_id": 9, "city_name": "Oakland", "county_id": 4},
    {"city_id": 10, "city_name": "Berkeley", "county_id": 4},
    {"city_id": 11, "city_name": "Fremont", "county_id": 4},
    # SoCal / LA County
    {"city_id": 12, "city_name": "Los Angeles", "county_id": 5},
    {"city_id": 13, "city_name": "Santa Monica", "county_id": 5},
    {"city_id": 14, "city_name": "Pasadena", "county_id": 5},
    {"city_id": 15, "city_name": "Beverly Hills", "county_id": 5},
    {"city_id": 16, "city_name": "Glendale", "county_id": 5},
    # SoCal / Orange County
    {"city_id": 17, "city_name": "Irvine", "county_id": 6},
    {"city_id": 18, "city_name": "Newport Beach", "county_id": 6},
    # SoCal / San Diego County
    {"city_id": 19, "city_name": "San Diego", "county_id": 7},
    {"city_id": 20, "city_name": "La Jolla", "county_id": 7},
    {"city_id": 21, "city_name": "Carlsbad", "county_id": 7},
    # SoCal / Ventura County
    {"city_id": 22, "city_name": "Thousand Oaks", "county_id": 12},
    # PNW / King County
    {"city_id": 23, "city_name": "Seattle", "county_id": 8},
    {"city_id": 24, "city_name": "Bellevue", "county_id": 8},
    {"city_id": 25, "city_name": "Redmond", "county_id": 8},
    {"city_id": 26, "city_name": "Kirkland", "county_id": 8},
    # PNW / Pierce County
    {"city_id": 27, "city_name": "Tacoma", "county_id": 9},
    # PNW / Snohomish County
    {"city_id": 28, "city_name": "Everett", "county_id": 10},
    {"city_id": 29, "city_name": "Bothell", "county_id": 10},
    # PNW / Kitsap
    {"city_id": 30, "city_name": "Bremerton", "county_id": 11},
]

# 60 zips: 24 Bay + 18 SoCal + 18 PNW.
# Temperature distribution: 18 HOT / 30 STABLE / 12 COOL.
# `price_multiplier` is the zip's price level relative to the market median.
ZIP_CODES_RAW = [
    # ==== Bay Area (24): 6 HOT / 14 STABLE / 4 COOL ====
    ("94102", 1, "HOT",     1.10),    # SoMa
    ("94103", 1, "STABLE",  1.00),
    ("94105", 1, "HOT",     1.30),    # FiDi/SoMa high end
    ("94107", 1, "STABLE",  1.25),    # Downgraded from HOT (Potrero)
    ("94108", 1, "STABLE",  1.15),
    ("94110", 1, "STABLE",  1.05),
    ("94117", 1, "STABLE",  1.20),    # Downgraded from HOT (Haight)
    ("94123", 1, "HOT",     1.35),    # Marina
    ("94014", 2, "COOL",    0.85),    # Daly City outskirts
    ("94061", 3, "STABLE",  1.05),
    ("94010", 4, "HOT",     1.40),    # Burlingame
    ("94301", 5, "HOT",     1.45),    # Palo Alto high end
    ("94303", 5, "STABLE",  1.30),    # East Palo Alto
    ("94040", 7, "STABLE",  1.25),    # Mountain View
    ("94041", 7, "STABLE",  1.10),
    ("94087", 8, "STABLE",  1.20),    # Sunnyvale
    ("95110", 6, "COOL",    0.90),    # Downtown San Jose
    ("95128", 6, "STABLE",  0.95),
    ("95014", 6, "HOT",     1.35),    # Cupertino
    ("94501", 11, "STABLE", 0.95),
    ("94601", 9, "COOL",    0.65),
    ("94605", 9, "STABLE",  0.85),
    ("94612", 9, "COOL",    0.75),
    ("94707", 10, "STABLE", 1.10),
    # ==== SoCal (18): 5 HOT / 10 STABLE / 3 COOL ====
    ("90017", 12, "STABLE", 0.90),
    ("90024", 12, "HOT",    1.30),    # Westwood
    ("90048", 12, "STABLE", 1.10),
    ("90069", 12, "HOT",    1.40),    # West Hollywood
    ("90210", 15, "HOT",    1.60),    # Beverly Hills
    ("90402", 13, "STABLE", 1.30),    # North Santa Monica
    ("90401", 13, "HOT",    1.20),    # Downtown Santa Monica
    ("91101", 14, "STABLE", 1.10),
    ("91201", 16, "COOL",   0.95),    # Glendale
    ("92602", 17, "STABLE", 1.05),
    ("92660", 18, "STABLE", 1.40),    # Newport Beach
    ("92691", 17, "STABLE", 1.00),
    ("92037", 20, "HOT",    1.45),    # La Jolla
    ("92101", 19, "STABLE", 0.95),
    ("92109", 19, "STABLE", 1.05),
    ("92122", 19, "STABLE", 1.15),    # UTC
    ("92008", 21, "COOL",   1.00),    # North Carlsbad
    ("91360", 22, "COOL",   0.80),    # Thousand Oaks
    # ==== PNW (18): 7 HOT / 6 STABLE / 5 COOL ====
    ("98101", 23, "STABLE", 1.05),
    ("98103", 23, "STABLE", 1.10),
    ("98105", 23, "HOT",    1.20),    # U-District/Ravenna
    ("98109", 23, "HOT",    1.20),    # Queen Anne
    ("98115", 23, "STABLE", 1.10),
    ("98119", 23, "HOT",    1.25),    # Queen Anne N
    ("98122", 23, "STABLE", 1.05),
    ("98004", 24, "HOT",    1.35),    # Bellevue
    ("98039", 24, "HOT",    1.50),    # Medina
    ("98052", 25, "HOT",    1.10),    # Redmond
    ("98033", 26, "HOT",    1.20),    # Kirkland
    ("98034", 26, "STABLE", 1.05),
    ("98401", 27, "COOL",   0.65),
    ("98402", 27, "COOL",   0.70),
    ("98404", 27, "COOL",   0.65),
    ("98201", 28, "COOL",   0.85),    # Everett
    ("98012", 29, "STABLE", 0.90),
    ("98310", 30, "COOL",   0.70),
]

ZIP_CODES = [
    {"zip_id": i + 1, "zip5": z[0], "city_id": z[1], "temperature": z[2], "price_multiplier": z[3]}
    for i, z in enumerate(ZIP_CODES_RAW)
]

PROPERTY_TYPES = ["SFR", "CONDO", "TOWNHOUSE", "MULTI_FAMILY"]
PROPERTY_TYPE_WEIGHTS = [0.55, 0.30, 0.10, 0.05]

LISTING_STATUS_CODES = ["ACT", "PND", "SLD", "EXP", "WTH"]
PIPELINE_STAGES = ["Lead", "Qualified", "Showing", "Offer", "Under Contract", "Closed Won", "Closed Lost"]
PIPELINE_STAGE_WEIGHTS = [0.10, 0.15, 0.15, 0.10, 0.10, 0.25, 0.15]

ACTIVITY_TYPES = ["CALL", "EMAIL", "SHOWING", "OPEN_HOUSE", "MEETING", "TEXT"]
ACTIVITY_TYPE_WEIGHTS = [0.30, 0.30, 0.15, 0.05, 0.10, 0.10]

SHOWING_TYPES = ["PRIVATE", "OPEN_HOUSE", "VIRTUAL"]
SHOWING_TYPE_WEIGHTS = [0.70, 0.20, 0.10]

DOM_PARAMS = {
    "HOT": (2.5, 0.5),
    "STABLE": (3.5, 0.7),
    "COOL": (4.2, 0.8),
}

SLR_CENTER = {"HOT": 1.04, "STABLE": 1.00, "COOL": 0.96}
SLR_SIGMA = {"HOT": 0.04, "STABLE": 0.03, "COOL": 0.04}

# ============================================================================
# SQLAlchemy ORM models
# ============================================================================


class Base(DeclarativeBase):
    pass


# --- Geographic dimensions ---

class GeoMarket(Base):
    __tablename__ = "geo_market"
    market_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    market_name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)


class GeoCounty(Base):
    __tablename__ = "geo_county"
    county_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    county_name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    market_id: Mapped[int] = mapped_column(ForeignKey("geo_market.market_id"), nullable=False)


class GeoCity(Base):
    __tablename__ = "geo_city"
    city_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_name: Mapped[str] = mapped_column(String(100), nullable=False)
    county_id: Mapped[int] = mapped_column(ForeignKey("geo_county.county_id"), nullable=False)


class GeoZipCode(Base):
    __tablename__ = "geo_zip_code"
    zip_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zip5: Mapped[str] = mapped_column(String(5), nullable=False, unique=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("geo_city.city_id"), nullable=False)
    temperature: Mapped[str] = mapped_column(String(10), nullable=False)
    price_multiplier: Mapped[float] = mapped_column(Float, nullable=False)


# --- MLS raw tables ---

class MlsProperty(Base):
    __tablename__ = "mls_property"
    PROPERTY_ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    STREET_NUM: Mapped[str] = mapped_column(String(20), nullable=False)
    STREET_NAME: Mapped[str] = mapped_column(String(200), nullable=False)
    UNIT_NUM: Mapped[str | None] = mapped_column(String(20))
    CITY: Mapped[str] = mapped_column(String(100), nullable=False)
    STATE: Mapped[str] = mapped_column(String(2), nullable=False)
    ZIP: Mapped[str] = mapped_column(String(10), nullable=False)
    zip_id: Mapped[int] = mapped_column(ForeignKey("geo_zip_code.zip_id"), nullable=False)
    PROPERTY_TYPE: Mapped[str] = mapped_column(String(20), nullable=False)
    BED_COUNT: Mapped[int] = mapped_column(Integer, nullable=False)
    BATH_COUNT: Mapped[float] = mapped_column(Float, nullable=False)
    SQFT: Mapped[int | None] = mapped_column(Integer)
    LOT_SQFT: Mapped[int | None] = mapped_column(Integer)
    YEAR_BUILT: Mapped[int | None] = mapped_column(Integer)
    HOA_FEE: Mapped[float | None] = mapped_column(Float)
    GARAGE_SPACES: Mapped[int | None] = mapped_column(Integer)
    CREATED_DT: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MlsListing(Base):
    __tablename__ = "mls_listing"
    LISTING_ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    MLS_NUMBER: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    PROPERTY_ID: Mapped[int] = mapped_column(ForeignKey("mls_property.PROPERTY_ID"), nullable=False)
    LIST_PRICE: Mapped[float] = mapped_column(Float, nullable=False)
    LIST_DT: Mapped[date] = mapped_column(Date, nullable=False)
    STATUS_CD: Mapped[str] = mapped_column(String(5), nullable=False)
    STATUS_DT: Mapped[date] = mapped_column(Date, nullable=False)
    DOM: Mapped[int | None] = mapped_column(Integer)
    LISTING_AGENT_LICENSE: Mapped[str] = mapped_column(String(20), nullable=False)
    LISTING_OFFICE_NAME: Mapped[str] = mapped_column(String(200), nullable=False)
    IS_CRESTLINE_LISTING: Mapped[bool] = mapped_column(Boolean, nullable=False)
    PUBLIC_REMARKS: Mapped[str | None] = mapped_column(Text)


class MlsListingEventHistory(Base):
    __tablename__ = "mls_listing_event_history"
    HISTORY_ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    LISTING_ID: Mapped[int] = mapped_column(ForeignKey("mls_listing.LISTING_ID"), nullable=False)
    EVENT_DT: Mapped[date] = mapped_column(Date, nullable=False)
    EVENT_TYPE: Mapped[str] = mapped_column(String(20), nullable=False)
    OLD_PRICE: Mapped[float | None] = mapped_column(Float)
    NEW_PRICE: Mapped[float | None] = mapped_column(Float)
    OLD_STATUS: Mapped[str | None] = mapped_column(String(5))
    NEW_STATUS: Mapped[str | None] = mapped_column(String(5))


class MlsSoldTransaction(Base):
    __tablename__ = "mls_sold_transaction"
    SOLD_ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    LISTING_ID: Mapped[int] = mapped_column(ForeignKey("mls_listing.LISTING_ID"), nullable=False)
    SALE_PRICE: Mapped[float] = mapped_column(Float, nullable=False)
    CLOSE_DT: Mapped[date] = mapped_column(Date, nullable=False)
    LIST_TO_SALE_RATIO: Mapped[float] = mapped_column(Float, nullable=False)
    BUYER_AGENT_LICENSE: Mapped[str] = mapped_column(String(20), nullable=False)
    LISTING_AGENT_LICENSE: Mapped[str] = mapped_column(String(20), nullable=False)
    FINANCING_TYPE: Mapped[str] = mapped_column(String(20), nullable=False)


class MlsPendingSale(Base):
    __tablename__ = "mls_pending_sale"
    PENDING_ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    LISTING_ID: Mapped[int] = mapped_column(ForeignKey("mls_listing.LISTING_ID"), nullable=False)
    CONTRACT_DT: Mapped[date] = mapped_column(Date, nullable=False)
    EXPECTED_CLOSE_DT: Mapped[date] = mapped_column(Date, nullable=False)
    CONTRACT_PRICE: Mapped[float] = mapped_column(Float, nullable=False)
    CONTINGENCIES: Mapped[str | None] = mapped_column(String(200))


class MlsListingShowing(Base):
    __tablename__ = "mls_listing_showing"
    SHOWING_ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    LISTING_ID: Mapped[int] = mapped_column(ForeignKey("mls_listing.LISTING_ID"), nullable=False)
    Agent_License__c: Mapped[str] = mapped_column(String(20), nullable=False)
    Contact_Id__c: Mapped[str | None] = mapped_column(ForeignKey("crm_contact.Id"))
    SHOWING_DT: Mapped[date] = mapped_column(Date, nullable=False)
    Showing_Type__c: Mapped[str] = mapped_column(String(20), nullable=False)
    Resulted_In_Offer__c: Mapped[bool] = mapped_column(Boolean, nullable=False)
    Notes__c: Mapped[str | None] = mapped_column(Text)


# --- CRM raw tables ---

class CrmOffice(Base):
    __tablename__ = "crm_office"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    Name: Mapped[str] = mapped_column(String(200), nullable=False)
    Market_Id__c: Mapped[int] = mapped_column(ForeignKey("geo_market.market_id"), nullable=False)
    Street__c: Mapped[str] = mapped_column(String(200), nullable=False)
    City__c: Mapped[str] = mapped_column(String(100), nullable=False)
    State__c: Mapped[str] = mapped_column(String(2), nullable=False)
    Zip__c: Mapped[str] = mapped_column(String(10), nullable=False)
    Opened_Date__c: Mapped[date] = mapped_column(Date, nullable=False)


class CrmAgent(Base):
    __tablename__ = "crm_agent"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    License_Number__c: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    First_Name__c: Mapped[str] = mapped_column(String(50), nullable=False)
    Last_Name__c: Mapped[str] = mapped_column(String(50), nullable=False)
    Email__c: Mapped[str] = mapped_column(String(200), nullable=False)
    Phone__c: Mapped[str | None] = mapped_column(String(30))
    Office_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_office.Id"), nullable=False)
    Hire_Date__c: Mapped[date] = mapped_column(Date, nullable=False)
    Termination_Date__c: Mapped[date | None] = mapped_column(Date)
    Commission_Split_Pct__c: Mapped[float] = mapped_column(Float, nullable=False)
    Tier__c: Mapped[str] = mapped_column(String(20), nullable=False)
    IsActive__c: Mapped[bool] = mapped_column(Boolean, nullable=False)
    LastModifiedDate: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CrmAgentZipCoverage(Base):
    __tablename__ = "crm_agent_zip_coverage"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    Agent_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_agent.Id"), nullable=False)
    Zip_Id__c: Mapped[int] = mapped_column(ForeignKey("geo_zip_code.zip_id"), nullable=False)
    Is_Primary__c: Mapped[bool] = mapped_column(Boolean, nullable=False)


class CrmContact(Base):
    __tablename__ = "crm_contact"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    FirstName: Mapped[str] = mapped_column(String(50), nullable=False)
    LastName: Mapped[str] = mapped_column(String(50), nullable=False)
    Email: Mapped[str | None] = mapped_column(String(200))
    Phone: Mapped[str | None] = mapped_column(String(30))
    Mailing_Street__c: Mapped[str | None] = mapped_column(String(200))
    Mailing_City__c: Mapped[str | None] = mapped_column(String(100))
    Mailing_State__c: Mapped[str | None] = mapped_column(String(2))
    Mailing_Zip__c: Mapped[str | None] = mapped_column(String(10))
    Contact_Type__c: Mapped[str] = mapped_column(String(20), nullable=False)
    Lead_Source__c: Mapped[str | None] = mapped_column(String(50))
    Preferred_Min_Price__c: Mapped[float | None] = mapped_column(Float)
    Preferred_Max_Price__c: Mapped[float | None] = mapped_column(Float)
    Preferred_Bed_Count__c: Mapped[int | None] = mapped_column(Integer)
    Preferred_Zip__c: Mapped[str | None] = mapped_column(String(10))
    Preferred_Property_Type__c: Mapped[str | None] = mapped_column(String(20))
    Owner_Agent_Id__c: Mapped[str | None] = mapped_column(ForeignKey("crm_agent.Id"))
    CreatedDate: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CrmOpportunity(Base):
    __tablename__ = "crm_opportunity"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    Name: Mapped[str] = mapped_column(String(200), nullable=False)
    Contact_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_contact.Id"), nullable=False)
    Owner_Agent_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_agent.Id"), nullable=False)
    Opportunity_Type__c: Mapped[str] = mapped_column(String(20), nullable=False)
    StageName: Mapped[str] = mapped_column(String(50), nullable=False)
    Amount: Mapped[float | None] = mapped_column(Float)
    CloseDate: Mapped[date | None] = mapped_column(Date)
    Listing_Id__c: Mapped[int | None] = mapped_column(ForeignKey("mls_listing.LISTING_ID"))
    Lost_Reason__c: Mapped[str | None] = mapped_column(String(100))
    CreatedDate: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CrmTransaction(Base):
    __tablename__ = "crm_transaction"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    Opportunity_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_opportunity.Id"), nullable=False)
    Sold_Id__c: Mapped[int | None] = mapped_column(ForeignKey("mls_sold_transaction.SOLD_ID"))
    Side__c: Mapped[str] = mapped_column(String(10), nullable=False)
    Sale_Price__c: Mapped[float] = mapped_column(Float, nullable=False)
    Gross_Commission__c: Mapped[float] = mapped_column(Float, nullable=False)
    Commission_Rate_Pct__c: Mapped[float] = mapped_column(Float, nullable=False)
    Contract_Date__c: Mapped[date] = mapped_column(Date, nullable=False)
    Close_Date__c: Mapped[date] = mapped_column(Date, nullable=False)
    Earnest_Money__c: Mapped[float | None] = mapped_column(Float)
    CreatedDate: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CrmAgentActivity(Base):
    __tablename__ = "crm_agent_activity"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    Agent_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_agent.Id"), nullable=False)
    Contact_Id__c: Mapped[str | None] = mapped_column(ForeignKey("crm_contact.Id"))
    Opportunity_Id__c: Mapped[str | None] = mapped_column(ForeignKey("crm_opportunity.Id"))
    Activity_Type__c: Mapped[str] = mapped_column(String(20), nullable=False)
    Activity_Date__c: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    Duration_Minutes__c: Mapped[int | None] = mapped_column(Integer)
    Notes__c: Mapped[str | None] = mapped_column(Text)
    Outcome__c: Mapped[str | None] = mapped_column(String(50))


class CrmCommissionSplit(Base):
    __tablename__ = "crm_commission_split"
    Id: Mapped[str] = mapped_column(String(20), primary_key=True)
    Transaction_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_transaction.Id"), nullable=False)
    Agent_Id__c: Mapped[str] = mapped_column(ForeignKey("crm_agent.Id"), nullable=False)
    Split_Pct__c: Mapped[float] = mapped_column(Float, nullable=False)
    Agent_Take__c: Mapped[float] = mapped_column(Float, nullable=False)
    Company_Take__c: Mapped[float] = mapped_column(Float, nullable=False)
    Payout_Date__c: Mapped[date | None] = mapped_column(Date)


# --- External data tables ---

class ExtZillowHomeValueIndex(Base):
    __tablename__ = "ext_zillow_home_value_index"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    RegionName: Mapped[str] = mapped_column(String(10), nullable=False)
    zip_id: Mapped[int] = mapped_column(ForeignKey("geo_zip_code.zip_id"), nullable=False)
    Date: Mapped[date] = mapped_column(Date, nullable=False)
    ZHVI: Mapped[float] = mapped_column(Float, nullable=False)
    ZHVI_MoM_Pct: Mapped[float | None] = mapped_column(Float)
    ZHVI_YoY_Pct: Mapped[float | None] = mapped_column(Float)


class ExtZillowMarketTemperature(Base):
    __tablename__ = "ext_zillow_market_temperature"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    RegionName: Mapped[str] = mapped_column(String(10), nullable=False)
    zip_id: Mapped[int] = mapped_column(ForeignKey("geo_zip_code.zip_id"), nullable=False)
    Date: Mapped[date] = mapped_column(Date, nullable=False)
    Market_Temperature: Mapped[str] = mapped_column(String(20), nullable=False)
    Sale_to_List_Ratio: Mapped[float] = mapped_column(Float, nullable=False)
    Median_DOM: Mapped[int] = mapped_column(Integer, nullable=False)


class ExtFreddieMacMortgageRate(Base):
    __tablename__ = "ext_freddie_mac_mortgage_rate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Week_End_Date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    Rate_30Y_Fixed: Mapped[float] = mapped_column(Float, nullable=False)
    Rate_15Y_Fixed: Mapped[float] = mapped_column(Float, nullable=False)
    Points_30Y: Mapped[float] = mapped_column(Float, nullable=False)


class ExtCensusDemographics(Base):
    __tablename__ = "ext_census_demographics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    county_id: Mapped[int] = mapped_column(ForeignKey("geo_county.county_id"), nullable=False)
    Year: Mapped[int] = mapped_column(Integer, nullable=False)
    Population: Mapped[int] = mapped_column(Integer, nullable=False)
    Median_Household_Income: Mapped[int] = mapped_column(Integer, nullable=False)
    Employment_Rate: Mapped[float] = mapped_column(Float, nullable=False)


class ExtWalkScore(Base):
    __tablename__ = "ext_walk_score"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    PROPERTY_ID: Mapped[int] = mapped_column(ForeignKey("mls_property.PROPERTY_ID"), nullable=False)
    Walk_Score: Mapped[int] = mapped_column(Integer, nullable=False)
    Transit_Score: Mapped[int] = mapped_column(Integer, nullable=False)
    Bike_Score: Mapped[int] = mapped_column(Integer, nullable=False)
    Score_Date: Mapped[date] = mapped_column(Date, nullable=False)


# ============================================================================
# Helper utility functions
# ============================================================================


def daterange_uniform(start: date, end: date) -> date:
    delta_days = max(1, (end - start).days)
    return start + timedelta(days=random.randint(0, delta_days))


def maybe_dirty_zip(zip5: str, dirty_prob: float = 0.05) -> str:
    if random.random() < dirty_prob:
        return f"{zip5}-{random.randint(1000, 9999)}"
    return zip5


def maybe_dirty_whitespace(s: str, dirty_prob: float = 0.03) -> str:
    if random.random() < dirty_prob:
        choice = random.choice(["lead", "trail", "case"])
        if choice == "lead":
            return " " + s
        elif choice == "trail":
            return s + " "
        else:
            return s.upper() if random.random() < 0.5 else s.lower()
    return s


def maybe_dirty_phone(phone: str, dirty_prob: float = 0.30) -> str:
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    if len(digits) < 10:
        return phone
    style = random.choice(["paren", "dash", "raw", "dot"])
    if style == "paren":
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif style == "dash":
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    elif style == "dot":
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"
    else:
        return digits


def pareto_distribute(items: list, weights_alpha: float = 0.8) -> list:
    """Pareto-distributed weights. The smaller alpha is, the heavier the tail.
       alpha=0.8 -> top 20% gets ~75-80% (used for activity volume)
       alpha=2.5 -> top 20% gets ~30-35% (used for transactions/opportunities)

    Note: the weights are returned in the original order of `items`, with no rank
    correlation to any item attribute. For weights correlated with tenure, use
    `tenure_weighted_pareto`.
    """
    n = len(items)
    raw = [random.paretovariate(weights_alpha) for _ in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


def tenure_weighted_pareto(
    agent_records: list[dict],
    weights_alpha: float = 2.5,
    rank_noise: float = 0.15,
) -> dict[str, float]:
    """Returns a dict {agent_id: weight} where agents with longer tenure get higher
    Pareto weights. `rank_noise` controls how much rank-swapping randomness is
    injected (0.0 = perfect rank correlation, 1.0 = completely random).

    Used for opportunity-ownership assignment so that the top GCI earners are
    reliably senior-tier agents instead of random ones.
    """
    n = len(agent_records)
    # Generate Pareto weights and sort descending (largest first)
    raw_weights = sorted([random.paretovariate(weights_alpha) for _ in range(n)], reverse=True)
    total = sum(raw_weights)
    norm_weights = [w / total for w in raw_weights]

    # Sort agents by tenure (longest tenure first)
    sorted_agents = sorted(agent_records, key=lambda a: a["Hire_Date__c"])

    # Inject realistic noise: swap a portion of agents with their neighbors,
    # so that a few junior agents can become top performers and vice versa
    swap_count = int(n * rank_noise)
    for _ in range(swap_count):
        i = random.randint(0, n - 2)
        sorted_agents[i], sorted_agents[i + 1] = sorted_agents[i + 1], sorted_agents[i]

    return {a["Id"]: w for a, w in zip(sorted_agents, norm_weights)}


def lognormal_dom(temperature: str) -> int:
    mu, sigma = DOM_PARAMS[temperature]
    return max(1, int(random.lognormvariate(mu, sigma)))


def pick_crestline_brokerage_variant() -> str:
    names, weights = zip(*CRESTLINE_BROKERAGE_VARIANTS)
    return random.choices(names, weights=weights, k=1)[0]


def mortgage_rate_at(d: date) -> float:
    """Real Freddie Mac PMMS 30-year rate trajectory (piecewise approximation).

    Anchors:
      2023-01: 6.48%
      2023-10: peak 7.79%
      2024-01: 6.69%
      2024-07: 6.95%
      2024-12: 6.60%
      2025-06: 6.75%
      2026-01: 6.50%
      2026-06: 6.55%
    """
    days = (d - DATA_START).days
    # Piecewise linear anchors (days since 2023-01-01, rate %)
    anchors = [
        (0,    6.48),    # 2023-01
        (180,  6.85),    # 2023-07
        (273,  7.79),    # 2023-10 peak
        (365,  6.69),    # 2024-01
        (548,  6.95),    # 2024-07
        (700,  6.60),    # 2024-12
        (730,  6.55),    # 2025-01
        (911,  6.75),    # 2025-06 (mid-year bump)
        (1095, 6.50),    # 2026-01
        (1250, 6.55),    # 2026-06
    ]
    # Locate the surrounding segment
    for i in range(len(anchors) - 1):
        d0, r0 = anchors[i]
        d1, r1 = anchors[i + 1]
        if d0 <= days <= d1:
            frac = (days - d0) / max(1, (d1 - d0))
            base = r0 + (r1 - r0) * frac
            break
    else:
        base = anchors[-1][1]
    noise = random.gauss(0, 0.04)
    return round(base + noise, 3)


# ============================================================================
# Reference data generators
# ============================================================================


def gen_geo_market() -> pl.DataFrame:
    return pl.DataFrame([
        {k: v for k, v in m.items() if k in ("market_id", "market_code", "market_name", "state")}
        for m in MARKETS
    ])


def gen_geo_county() -> pl.DataFrame:
    return pl.DataFrame(COUNTIES)


def gen_geo_city() -> pl.DataFrame:
    return pl.DataFrame(CITIES)


def gen_geo_zip_code() -> pl.DataFrame:
    return pl.DataFrame(ZIP_CODES)


def _market_id_for_zip(zip_id: int) -> int:
    z = next(z for z in ZIP_CODES if z["zip_id"] == zip_id)
    c = next(c for c in CITIES if c["city_id"] == z["city_id"])
    co = next(co for co in COUNTIES if co["county_id"] == c["county_id"])
    return co["market_id"]


# ============================================================================
# MLS generators
# ============================================================================


def gen_mls_property(n: int) -> pl.DataFrame:
    records = []
    # Zip weights: HOT zips have slightly more inventory
    zip_weights = []
    for z in ZIP_CODES:
        if z["temperature"] == "HOT":
            zip_weights.append(1.5)
        elif z["temperature"] == "STABLE":
            zip_weights.append(1.2)
        else:
            zip_weights.append(0.7)

    for i in range(1, n + 1):
        zip_row = random.choices(ZIP_CODES, weights=zip_weights, k=1)[0]
        city = next(c for c in CITIES if c["city_id"] == zip_row["city_id"])
        market_id = _market_id_for_zip(zip_row["zip_id"])
        ptype = random.choices(PROPERTY_TYPES, weights=PROPERTY_TYPE_WEIGHTS, k=1)[0]
        bed = max(1, int(random.gauss(3, 1)))
        bath = max(1.0, round(random.gauss(bed * 0.8, 0.5) * 2) / 2)
        sqft = None if random.random() < 0.08 else max(400, int(random.gauss(1800, 600)))
        lot = None if ptype == "CONDO" else max(1000, int(random.gauss(6000, 3000)))
        year_built = None if random.random() < 0.10 else random.randint(1900, 2024)
        hoa = round(random.uniform(150, 800), 2) if ptype in ("CONDO", "TOWNHOUSE") else None
        garage = None if random.random() < 0.05 else random.randint(0, 3)

        street_name = maybe_dirty_whitespace(fake.street_name(), dirty_prob=0.05)
        records.append({
            "PROPERTY_ID": i,
            "STREET_NUM": str(random.randint(100, 9999)),
            "STREET_NAME": street_name,
            "UNIT_NUM": f"#{random.randint(1, 999)}" if ptype == "CONDO" and random.random() < 0.7 else None,
            "CITY": city["city_name"],
            "STATE": "WA" if market_id == 3 else "CA",
            "ZIP": maybe_dirty_zip(zip_row["zip5"]),
            "zip_id": zip_row["zip_id"],
            "PROPERTY_TYPE": ptype,
            "BED_COUNT": bed,
            "BATH_COUNT": bath,
            "SQFT": sqft,
            "LOT_SQFT": lot,
            "YEAR_BUILT": year_built,
            "HOA_FEE": hoa,
            "GARAGE_SPACES": garage,
            "CREATED_DT": fake.date_time_between(start_date=DATA_START, end_date=DATA_END),
        })
    return pl.DataFrame(records)


def gen_mls_listing(n: int, properties_df: pl.DataFrame, crestline_licenses: list[str]) -> pl.DataFrame:
    """Generate listings with MLS-CRM coupling.

    ~30% of listings have LISTING_OFFICE_NAME = a Crestline variant, with the
    LISTING_AGENT_LICENSE drawn from crestline_licenses (Pareto-weighted).
    The remaining 70% use a competitor brokerage and a DRE9{nnnnn} license.
    """
    prop_records = properties_df.to_dicts()
    crestline_license_weights = pareto_distribute(crestline_licenses)

    records = []
    listing_id = 1
    mls_seq = 100000

    # Pre-allocate the number of listings per property (mean ~1.6)
    target_per_prop = []
    while len(target_per_prop) < len(prop_records):
        target_per_prop.append(max(1, int(random.gauss(1.6, 0.7))))
    cum = 0
    final_targets = []
    for t in target_per_prop:
        if cum + t > n:
            t = n - cum
        if t <= 0:
            break
        final_targets.append(t)
        cum += t
    while cum < n:
        idx = random.randint(0, len(final_targets) - 1)
        final_targets[idx] += 1
        cum += 1

    # Year weights matching the macro narrative (2024 volume decline)
    year_weights = {2023: 1.00, 2024: 0.72, 2025: 0.85, 2026: 0.50}

    for prop_idx, num_listings in enumerate(final_targets):
        if prop_idx >= len(prop_records):
            break
        prop = prop_records[prop_idx]
        zip_row = next(z for z in ZIP_CODES if z["zip_id"] == prop["zip_id"])
        temperature = zip_row["temperature"]
        price_mult = zip_row["price_multiplier"]
        market_id = _market_id_for_zip(prop["zip_id"])
        market = next(m for m in MARKETS if m["market_id"] == market_id)

        sqft = prop["SQFT"] or 1800
        base_psf = (market["median_price"] / 1800) * price_mult
        base_price = sqft * base_psf * random.gauss(1.0, 0.12)
        base_price *= 1 + (prop["BED_COUNT"] - 3) * 0.08

        list_dates = []
        for _ in range(num_listings):
            year = random.choices(list(year_weights.keys()), weights=list(year_weights.values()), k=1)[0]
            if year == 2026:
                end_d = date(2026, 6, 5)
            else:
                end_d = date(year, 12, 31)
            start_d = date(year, 1, 1)
            list_dates.append(daterange_uniform(start_d, end_d))
        list_dates.sort()

        for list_dt in list_dates:
            years_elapsed = (list_dt - DATA_START).days / 365.25
            appreciated = base_price * (1.04 ** years_elapsed) * random.uniform(0.92, 1.10)
            list_price = round(appreciated / 1000) * 1000

            dom = lognormal_dom(temperature)
            status_dt = list_dt + timedelta(days=dom)
            if status_dt > CURRENT_DATE:
                status_dt = CURRENT_DATE
                dom = (status_dt - list_dt).days

            r = random.random()
            if r < 0.62:
                status_cd = "SLD"
            elif r < 0.68:
                status_cd = "PND"
            elif r < 0.83:
                status_cd = "EXP"
            elif r < 0.93:
                status_cd = "WTH"
            else:
                status_cd = "ACT"
                status_dt = list_dt
                dom = (CURRENT_DATE - list_dt).days

            # MLS-CRM coupling: 30% Crestline, 70% competitors
            is_crestline = random.random() < CRESTLINE_BROKERAGE_SHARE
            if is_crestline:
                office_name = pick_crestline_brokerage_variant()
                agent_license = random.choices(crestline_licenses, weights=crestline_license_weights, k=1)[0]
            else:
                office_name = random.choice(COMPETITOR_BROKERAGES)
                agent_license = f"DRE9{random.randint(10000, 99999)}"

            records.append({
                "LISTING_ID": listing_id,
                "MLS_NUMBER": f"ML{mls_seq:08d}",
                "PROPERTY_ID": prop["PROPERTY_ID"],
                "LIST_PRICE": list_price,
                "LIST_DT": list_dt,
                "STATUS_CD": status_cd,
                "STATUS_DT": status_dt,
                "DOM": dom,
                "LISTING_AGENT_LICENSE": agent_license,
                "LISTING_OFFICE_NAME": office_name,
                "IS_CRESTLINE_LISTING": is_crestline,
                "PUBLIC_REMARKS": fake.sentence(nb_words=12) if random.random() > 0.05 else None,
            })
            listing_id += 1
            mls_seq += 1
            if listing_id > n:
                break
        if listing_id > n:
            break

    return pl.DataFrame(records)


def gen_mls_listing_event_history(target_n: int, listings_df: pl.DataFrame) -> pl.DataFrame:
    listings = listings_df.to_dicts()
    records = []
    history_id = 1

    for lst in listings:
        records.append({
            "HISTORY_ID": history_id,
            "LISTING_ID": lst["LISTING_ID"],
            "EVENT_DT": lst["LIST_DT"],
            "EVENT_TYPE": "STATUS_CHANGE",
            "OLD_PRICE": None,
            "NEW_PRICE": lst["LIST_PRICE"],
            "OLD_STATUS": None,
            "NEW_STATUS": "ACT",
        })
        history_id += 1

        n_changes = random.choices([0, 1, 2, 3], weights=[0.45, 0.30, 0.18, 0.07], k=1)[0]
        current_price = lst["LIST_PRICE"]
        dom = lst["DOM"] or 30
        if dom <= 0:
            dom = 1
        for chg in range(n_changes):
            days_in = random.randint(1, max(1, dom - 1))
            event_dt = lst["LIST_DT"] + timedelta(days=days_in)
            new_price = current_price * random.uniform(0.92, 0.99)
            new_price = round(new_price / 1000) * 1000
            records.append({
                "HISTORY_ID": history_id,
                "LISTING_ID": lst["LISTING_ID"],
                "EVENT_DT": event_dt,
                "EVENT_TYPE": "PRICE_CHANGE",
                "OLD_PRICE": current_price,
                "NEW_PRICE": new_price,
                "OLD_STATUS": "ACT",
                "NEW_STATUS": "ACT",
            })
            history_id += 1
            current_price = new_price

        if lst["STATUS_CD"] != "ACT":
            records.append({
                "HISTORY_ID": history_id,
                "LISTING_ID": lst["LISTING_ID"],
                "EVENT_DT": lst["STATUS_DT"],
                "EVENT_TYPE": "STATUS_CHANGE",
                "OLD_PRICE": current_price,
                "NEW_PRICE": current_price,
                "OLD_STATUS": "ACT",
                "NEW_STATUS": lst["STATUS_CD"],
            })
            history_id += 1

        if len(records) >= target_n:
            break

    return pl.DataFrame(records[:target_n])


def gen_mls_sold_transaction(
    listings_df: pl.DataFrame,
    properties_df: pl.DataFrame,
    crestline_licenses: list[str],
) -> pl.DataFrame:
    """One sold-transaction row per SLD listing. The buyer license is Crestline with 30% probability."""
    prop_to_zip = dict(zip(properties_df["PROPERTY_ID"].to_list(), properties_df["zip_id"].to_list()))
    zip_to_temp = {z["zip_id"]: z["temperature"] for z in ZIP_CODES}

    sold_listings = listings_df.filter(pl.col("STATUS_CD") == "SLD").to_dicts()
    records = []
    for idx, lst in enumerate(sold_listings, start=1):
        zip_id = prop_to_zip.get(lst["PROPERTY_ID"])
        temp = zip_to_temp.get(zip_id, "STABLE")
        slr_center = SLR_CENTER[temp]
        slr_sigma = SLR_SIGMA[temp]
        slr = max(0.80, min(1.30, random.gauss(slr_center, slr_sigma)))
        sale_price = round(lst["LIST_PRICE"] * slr / 1000) * 1000
        close_dt = lst["STATUS_DT"]
        listing_agent = lst["LISTING_AGENT_LICENSE"]

        # Buyer agent: 30% Crestline, 70% competitors
        if random.random() < CRESTLINE_BROKERAGE_SHARE:
            buyer_agent = random.choice(crestline_licenses)
        else:
            buyer_agent = f"DRE9{random.randint(10000, 99999)}"

        financing = random.choices(
            ["CASH", "CONVENTIONAL", "FHA", "VA", "JUMBO"],
            weights=[0.25, 0.45, 0.10, 0.05, 0.15],
            k=1,
        )[0]
        records.append({
            "SOLD_ID": idx,
            "LISTING_ID": lst["LISTING_ID"],
            "SALE_PRICE": sale_price,
            "CLOSE_DT": close_dt,
            "LIST_TO_SALE_RATIO": round(slr, 4),
            "BUYER_AGENT_LICENSE": buyer_agent,
            "LISTING_AGENT_LICENSE": listing_agent,
            "FINANCING_TYPE": financing,
        })
    return pl.DataFrame(records)


def gen_mls_pending_sale(listings_df: pl.DataFrame, target_n: int) -> pl.DataFrame:
    """`pending_sale` is a current snapshot, so contract dates must be recent
    (within ~60 days before CURRENT_DATE -- a typical escrow window)."""
    snapshot_cutoff = CURRENT_DATE - timedelta(days=60)
    pnd_listings = listings_df.filter(
        (pl.col("STATUS_CD") == "PND") & (pl.col("STATUS_DT") >= snapshot_cutoff)
    ).to_dicts()
    if len(pnd_listings) < target_n:
        target_n = len(pnd_listings)
    chosen = random.sample(pnd_listings, target_n) if target_n > 0 else []
    records = []
    for idx, lst in enumerate(chosen, start=1):
        contract_dt = lst["STATUS_DT"]
        expected_close = contract_dt + timedelta(days=random.randint(20, 45))
        contract_price = lst["LIST_PRICE"] * random.uniform(0.96, 1.02)
        contingencies = random.choice([
            None, "INSPECTION", "FINANCING", "APPRAISAL",
            "INSPECTION;FINANCING", "INSPECTION;APPRAISAL",
        ])
        records.append({
            "PENDING_ID": idx,
            "LISTING_ID": lst["LISTING_ID"],
            "CONTRACT_DT": contract_dt,
            "EXPECTED_CLOSE_DT": expected_close,
            "CONTRACT_PRICE": round(contract_price / 1000) * 1000,
            "CONTINGENCIES": contingencies,
        })
    return pl.DataFrame(records) if records else pl.DataFrame(schema={
        "PENDING_ID": pl.Int64, "LISTING_ID": pl.Int64, "CONTRACT_DT": pl.Date,
        "EXPECTED_CLOSE_DT": pl.Date, "CONTRACT_PRICE": pl.Float64, "CONTINGENCIES": pl.Utf8,
    })


def gen_mls_listing_showing(
    target_n: int,
    listings_df: pl.DataFrame,
    properties_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
    crestline_licenses: list[str],
) -> pl.DataFrame:
    """Number of showings per listing -- more for HOT zips, fewer for COOL zips."""
    prop_to_zip = dict(zip(properties_df["PROPERTY_ID"].to_list(), properties_df["zip_id"].to_list()))
    zip_to_temp = {z["zip_id"]: z["temperature"] for z in ZIP_CODES}
    contact_ids = contacts_df["Id"].to_list()

    listings = listings_df.filter(pl.col("STATUS_CD").is_in(["SLD", "PND", "ACT", "EXP", "WTH"])).to_dicts()
    records = []
    showing_id = 1

    # Per design decision 7
    showings_target_per_listing = {"HOT": 2.5, "STABLE": 1.5, "COOL": 0.6}

    for lst in listings:
        zip_id = prop_to_zip.get(lst["PROPERTY_ID"])
        temp = zip_to_temp.get(zip_id, "STABLE")
        mean_showings = showings_target_per_listing[temp]
        # Use round() (not int()) to avoid truncation bias pulling the mean down
        n_showings = max(0, round(random.gauss(mean_showings, 1.0)))

        # Window: from LIST_DT to min(STATUS_DT, CURRENT_DATE)
        start_d = lst["LIST_DT"]
        end_d = min(lst["STATUS_DT"], CURRENT_DATE)
        if end_d <= start_d:
            end_d = start_d + timedelta(days=1)

        for _ in range(n_showings):
            showing_dt = daterange_uniform(start_d, end_d)
            # Showing agent: 30% Crestline (matching the brokerage share)
            if random.random() < CRESTLINE_BROKERAGE_SHARE:
                agent_license = random.choice(crestline_licenses)
                # When it's a Crestline agent, 60% chance of being tied to a contact
                contact_id = random.choice(contact_ids) if random.random() < 0.6 else None
            else:
                agent_license = f"DRE9{random.randint(10000, 99999)}"
                contact_id = None

            showing_type = random.choices(SHOWING_TYPES, weights=SHOWING_TYPE_WEIGHTS, k=1)[0]
            # Offer probability: higher for listings that eventually close
            offer_prob = 0.10 if lst["STATUS_CD"] != "SLD" else 0.20
            resulted_in_offer = random.random() < offer_prob

            records.append({
                "SHOWING_ID": showing_id,
                "LISTING_ID": lst["LISTING_ID"],
                "Agent_License__c": agent_license,
                "Contact_Id__c": contact_id,
                "SHOWING_DT": showing_dt,
                "Showing_Type__c": showing_type,
                "Resulted_In_Offer__c": resulted_in_offer,
                "Notes__c": fake.sentence(nb_words=6) if random.random() > 0.4 else None,
            })
            showing_id += 1
            if showing_id > target_n:
                return pl.DataFrame(records)
    return pl.DataFrame(records)


# ============================================================================
# CRM generators
# ============================================================================


def gen_crm_office() -> pl.DataFrame:
    offices = []
    office_data = [
        ("SF Headquarters", 1, "SoMa District", "San Francisco", "94105"),
        ("Palo Alto", 1, "University Ave", "Palo Alto", "94301"),
        ("Oakland", 1, "Broadway", "Oakland", "94612"),
        ("Los Angeles", 2, "Wilshire Blvd", "Los Angeles", "90017"),
        ("Santa Monica", 2, "Ocean Ave", "Santa Monica", "90401"),
        ("San Diego", 2, "Broadway", "San Diego", "92101"),
        ("Seattle", 3, "Pike Street", "Seattle", "98101"),
        ("Bellevue", 3, "Bellevue Way", "Bellevue", "98004"),
    ]
    # Offices opened in 2017, before the earliest agent hire date (2018-01),
    # so every agent's Hire_Date__c >= their office's Opened_Date__c.
    for idx, (name, mkt_id, street, city, zip5) in enumerate(office_data, start=1):
        offices.append({
            "Id": f"OFF{idx:05d}",
            "Name": f"Crestline Realty - {name}",
            "Market_Id__c": mkt_id,
            "Street__c": street,
            "City__c": city,
            "State__c": "WA" if mkt_id == 3 else "CA",
            "Zip__c": zip5,
            "Opened_Date__c": date(2017, random.randint(1, 12), random.randint(1, 28)),
        })
    return pl.DataFrame(offices)


def gen_crm_agent(n: int, offices_df: pl.DataFrame) -> pl.DataFrame:
    office_ids = offices_df["Id"].to_list()
    records = []
    for i in range(1, n + 1):
        first = fake.first_name()
        last = fake.last_name()
        license_num = f"DRE{i:05d}"
        hire_dt = fake.date_between(start_date=date(2018, 1, 1), end_date=date(2025, 6, 30))
        tenure_years = (CURRENT_DATE - hire_dt).days / 365.25

        if tenure_years < 2:
            tier = "JUNIOR"
            split = round(random.uniform(0.65, 0.72), 3)
        elif tenure_years < 5:
            tier = "MID"
            split = round(random.uniform(0.72, 0.80), 3)
        else:
            tier = "SENIOR"
            split = round(random.uniform(0.80, 0.88), 3)

        if random.random() < 0.10 and hire_dt < date(2024, 1, 1):
            term_dt = fake.date_between(start_date=hire_dt + timedelta(days=180), end_date=CURRENT_DATE)
            is_active = False
        else:
            term_dt = None
            is_active = True

        phone = maybe_dirty_phone(fake.phone_number(), dirty_prob=0.4)
        records.append({
            "Id": f"AGT{i:05d}",
            "License_Number__c": license_num,
            "First_Name__c": first,
            "Last_Name__c": last,
            "Email__c": f"{first.lower()}.{last.lower()}{i}@crestlinerealty.com",
            "Phone__c": phone,
            "Office_Id__c": random.choice(office_ids),
            "Hire_Date__c": hire_dt,
            "Termination_Date__c": term_dt,
            "Commission_Split_Pct__c": split,
            "Tier__c": tier,
            "IsActive__c": is_active,
            "LastModifiedDate": fake.date_time_between(start_date=hire_dt, end_date=CURRENT_DATE),
        })
    return pl.DataFrame(records)


def gen_crm_agent_zip_coverage(agents_df: pl.DataFrame, target_n: int) -> pl.DataFrame:
    agent_ids = agents_df["Id"].to_list()
    zip_ids = [z["zip_id"] for z in ZIP_CODES]
    records = []
    seq = 1
    for agent_id in agent_ids:
        n_zips = random.choices([1, 2, 3, 4, 5], weights=[0.20, 0.35, 0.25, 0.15, 0.05], k=1)[0]
        chosen_zips = random.sample(zip_ids, min(n_zips, len(zip_ids)))
        for idx, zip_id in enumerate(chosen_zips):
            records.append({
                "Id": f"AZC{seq:06d}",
                "Agent_Id__c": agent_id,
                "Zip_Id__c": zip_id,
                "Is_Primary__c": (idx == 0),
            })
            seq += 1
            if len(records) >= target_n:
                break
        if len(records) >= target_n:
            break
    return pl.DataFrame(records)


def gen_crm_contact(n: int, agents_df: pl.DataFrame) -> pl.DataFrame:
    active_agents = agents_df.filter(pl.col("IsActive__c")).to_dicts()
    active_agent_ids = [a["Id"] for a in active_agents]
    records = []

    n_dups = int(n * 0.03)
    n_originals = n - n_dups

    for i in range(1, n_originals + 1):
        first = fake.first_name()
        last = fake.last_name()
        contact_type = random.choices(
            ["Buyer", "Seller", "Both", "Lead"], weights=[0.40, 0.25, 0.10, 0.25], k=1
        )[0]
        email = None if random.random() < 0.10 else f"{first.lower()}.{last.lower()}{random.randint(1, 9999)}@{fake.free_email_domain()}"
        phone = None if random.random() < 0.05 else maybe_dirty_phone(fake.phone_number(), dirty_prob=0.5)
        zip_row = random.choice(ZIP_CODES)
        city = next(c for c in CITIES if c["city_id"] == zip_row["city_id"])

        if contact_type in ("Buyer", "Both"):
            market = next(m for m in MARKETS if m["market_id"] == _market_id_for_zip(zip_row["zip_id"]))
            mid = market["median_price"] * zip_row["price_multiplier"]
            pref_min = round(mid * random.uniform(0.65, 0.90) / 10000) * 10000
            pref_max = round(mid * random.uniform(1.05, 1.40) / 10000) * 10000
            pref_bed = random.choice([2, 3, 3, 4, 4, 5])
            # 70% have a single preferred zip, 30% NULL (open to any zip)
            pref_zip = zip_row["zip5"] if random.random() < 0.7 else None
            pref_ptype = random.choices(
                ["SFR", "CONDO", "TOWNHOUSE", "MULTI_FAMILY", "ANY"],
                weights=[0.40, 0.25, 0.15, 0.05, 0.15], k=1,
            )[0]
        else:
            pref_min = pref_max = pref_bed = pref_zip = pref_ptype = None

        records.append({
            "Id": f"CON{i:06d}",
            "FirstName": maybe_dirty_whitespace(first, dirty_prob=0.04),
            "LastName": last,
            "Email": email,
            "Phone": phone,
            "Mailing_Street__c": fake.street_address(),
            "Mailing_City__c": city["city_name"],
            "Mailing_State__c": "WA" if _market_id_for_zip(zip_row["zip_id"]) == 3 else "CA",
            "Mailing_Zip__c": maybe_dirty_zip(zip_row["zip5"]),
            "Contact_Type__c": contact_type,
            "Lead_Source__c": random.choice(["Web", "Referral", "Open House", "Cold Call", "Repeat Client", None]),
            "Preferred_Min_Price__c": pref_min,
            "Preferred_Max_Price__c": pref_max,
            "Preferred_Bed_Count__c": pref_bed,
            "Preferred_Zip__c": pref_zip,
            "Preferred_Property_Type__c": pref_ptype,
            "Owner_Agent_Id__c": random.choice(active_agent_ids) if random.random() > 0.05 else None,
            "CreatedDate": fake.date_time_between(start_date=DATA_START, end_date=CURRENT_DATE),
        })

    # Near-duplicates
    for j in range(n_dups):
        src = random.choice(records)
        dup = dict(src)
        dup["Id"] = f"CON{n_originals + j + 1:06d}"
        if dup["FirstName"] and len(dup["FirstName"].strip()) > 1:
            stripped = dup["FirstName"].strip()
            dup["FirstName"] = stripped[0] + "." + stripped[1:]
        dup["CreatedDate"] = fake.date_time_between(start_date=DATA_START, end_date=CURRENT_DATE)
        records.append(dup)

    return pl.DataFrame(records)


def gen_crm_opportunity(
    n: int, contacts_df: pl.DataFrame, agents_df: pl.DataFrame, listings_df: pl.DataFrame
) -> pl.DataFrame:
    contact_ids = contacts_df["Id"].to_list()
    active_agents = agents_df.filter(pl.col("IsActive__c")).to_dicts()
    active_agent_ids = [a["Id"] for a in active_agents]
    # Opportunity ownership uses a TENURE-correlated Pareto so that Query 3 (Top GCI)
    # reflects senior agents leading, and Query 15 (Tenure vs Earnings) shows a real
    # monotonic increase (not just an artifact of the tier-based split percentages).
    weight_map = tenure_weighted_pareto(active_agents, weights_alpha=2.5, rank_noise=0.15)
    weights = [weight_map[id] for id in active_agent_ids]
    # Listing FK only points to Crestline-owned listings
    crestline_listings = listings_df.filter(pl.col("IS_CRESTLINE_LISTING") == True)["LISTING_ID"].to_list()

    records = []
    for i in range(1, n + 1):
        contact_id = random.choice(contact_ids)
        agent_id = random.choices(active_agent_ids, weights=weights, k=1)[0]
        opp_type = random.choice(["Buyer", "Seller"])
        stage = random.choices(PIPELINE_STAGES, weights=PIPELINE_STAGE_WEIGHTS, k=1)[0]

        # First pick created_dt, then pick close_dt >= created_dt (typical lifecycle 10-180 days)
        created_dt = fake.date_time_between(start_date=DATA_START, end_date=CURRENT_DATE)
        created_d = created_dt.date() if hasattr(created_dt, "date") else created_dt

        if stage == "Closed Won":
            min_close = created_d + timedelta(days=10)
            if min_close > CURRENT_DATE:
                min_close = CURRENT_DATE
            max_close = min(created_d + timedelta(days=180), CURRENT_DATE)
            if max_close < min_close:
                max_close = min_close
            close_dt = fake.date_between(start_date=min_close, end_date=max_close)
            linked_listing = random.choice(crestline_listings) if random.random() > 0.1 and crestline_listings else None
            amount = round(random.uniform(500_000, 2_500_000) / 1000) * 1000
            lost_reason = None
        elif stage == "Closed Lost":
            min_close = created_d + timedelta(days=5)
            if min_close > CURRENT_DATE:
                min_close = CURRENT_DATE
            max_close = min(created_d + timedelta(days=120), CURRENT_DATE)
            if max_close < min_close:
                max_close = min_close
            close_dt = fake.date_between(start_date=min_close, end_date=max_close)
            linked_listing = None
            amount = None
            lost_reason = random.choice([
                "Price too high", "Lost to competitor", "Financing fell through",
                "Inspection issues", "Buyer changed mind", "No response",
            ])
        else:
            close_dt = None
            linked_listing = random.choice(crestline_listings) if random.random() > 0.4 and crestline_listings else None
            amount = round(random.uniform(500_000, 2_500_000) / 1000) * 1000 if random.random() > 0.3 else None
            lost_reason = None

        records.append({
            "Id": f"OPP{i:06d}",
            "Name": f"{opp_type} Opportunity - {fake.last_name()}",
            "Contact_Id__c": contact_id,
            "Owner_Agent_Id__c": agent_id,
            "Opportunity_Type__c": opp_type,
            "StageName": stage,
            "Amount": amount,
            "CloseDate": close_dt,
            "Listing_Id__c": linked_listing,
            "Lost_Reason__c": lost_reason,
            "CreatedDate": created_dt,
        })
    return pl.DataFrame(records)


def gen_crm_transaction(
    target_n: int,
    opportunities_df: pl.DataFrame,
    sold_df: pl.DataFrame,
    listings_df: pl.DataFrame,
) -> pl.DataFrame:
    """One transaction per Closed-Won opportunity.

    Semantic invariants:
      - Side__c is derived from opp.Opportunity_Type__c (Buyer opp -> BUYER side, etc.)
      - Sold_Id__c is aligned with opp.Listing_Id__c when it exists (matches the sold
        record for that listing); otherwise it's drawn from the remaining pool of
        Crestline-listed sold records.
    """
    won_opps = opportunities_df.filter(pl.col("StageName") == "Closed Won").to_dicts()
    sold_records = sold_df.to_dicts()
    crestline_listing_ids = set(listings_df.filter(pl.col("IS_CRESTLINE_LISTING") == True)["LISTING_ID"].to_list())

    # Build lookups: listing_id -> sold record (used for opp.Listing_Id__c alignment)
    sold_by_listing = {s["LISTING_ID"]: s for s in sold_records}
    sold_by_id = {s["SOLD_ID"]: s for s in sold_records}
    # Pool of remaining Crestline sold IDs (used for opps without a listing link)
    aligned_sold_ids: set[int] = set()
    fallback_pool = [s["SOLD_ID"] for s in sold_records if s["LISTING_ID"] in crestline_listing_ids]
    random.shuffle(fallback_pool)
    fallback_iter = iter(fallback_pool)

    records = []
    for idx, opp in enumerate(won_opps, start=1):
        if idx > target_n:
            break

        # Sold_Id__c alignment
        sold_id = None
        matched = None
        if opp["Listing_Id__c"] is not None and opp["Listing_Id__c"] in sold_by_listing:
            candidate = sold_by_listing[opp["Listing_Id__c"]]
            if candidate["SOLD_ID"] not in aligned_sold_ids:
                sold_id = candidate["SOLD_ID"]
                matched = candidate
                aligned_sold_ids.add(sold_id)
        if matched is None:
            # Fall back to an unused Crestline sold record
            for candidate_id in fallback_iter:
                if candidate_id not in aligned_sold_ids:
                    sold_id = candidate_id
                    matched = sold_by_id[candidate_id]
                    aligned_sold_ids.add(sold_id)
                    break

        if matched is not None:
            sale_price = matched["SALE_PRICE"]
            close_dt = matched["CLOSE_DT"]
        else:
            sold_id = None
            sale_price = opp["Amount"] or round(random.uniform(500_000, 2_000_000) / 1000) * 1000
            close_dt = opp["CloseDate"] or fake.date_between(start_date=DATA_START, end_date=CURRENT_DATE)

        commission_rate = round(random.uniform(2.5, 3.0), 2)
        gross_commission = round(sale_price * commission_rate / 100, 2)
        contract_dt = close_dt - timedelta(days=random.randint(20, 45))

        side = "BUYER" if opp["Opportunity_Type__c"] == "Buyer" else "SELLER"

        records.append({
            "Id": f"TXN{idx:06d}",
            "Opportunity_Id__c": opp["Id"],
            "Sold_Id__c": sold_id,
            "Side__c": side,
            "Sale_Price__c": sale_price,
            "Gross_Commission__c": gross_commission,
            "Commission_Rate_Pct__c": commission_rate,
            "Contract_Date__c": contract_dt,
            "Close_Date__c": close_dt,
            "Earnest_Money__c": round(sale_price * random.uniform(0.01, 0.03), 2),
            "CreatedDate": fake.date_time_between(start_date=contract_dt, end_date=close_dt + timedelta(days=5)),
        })
    return pl.DataFrame(records)


def gen_crm_agent_activity(
    n: int,
    agents_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
    opportunities_df: pl.DataFrame,
) -> pl.DataFrame:
    """Activity_Date__c is bounded by each agent's tenure window
    [Hire_Date__c, Termination_Date__c or CURRENT_DATE]."""
    agent_records = agents_df.to_dicts()
    agent_by_id = {a["Id"]: a for a in agent_records}
    active_agents = [a for a in agent_records if a["IsActive__c"]]
    active_agent_ids = [a["Id"] for a in active_agents]
    agent_weights = pareto_distribute(active_agent_ids)
    contact_ids = contacts_df["Id"].to_list()

    # Per decision 2: ~40% of opp links are NULL, and ~10% of the rest point to Lost opps (still a valid FK, soft "stale" signal)
    opp_records = opportunities_df.to_dicts()
    all_opp_ids = [o["Id"] for o in opp_records]
    lost_opp_ids = [o["Id"] for o in opp_records if o["StageName"] == "Closed Lost"]

    records = []
    for i in range(1, n + 1):
        agent_id = random.choices(active_agent_ids, weights=agent_weights, k=1)[0]
        agent = agent_by_id[agent_id]
        contact_id = random.choice(contact_ids) if random.random() > 0.1 else None

        # Opportunity selection with soft-staleness
        r = random.random()
        if r < 0.40:
            opp_id = None
        elif r < 0.50:
            opp_id = random.choice(lost_opp_ids) if lost_opp_ids else random.choice(all_opp_ids)
        else:
            opp_id = random.choice(all_opp_ids)

        activity_type = random.choices(ACTIVITY_TYPES, weights=ACTIVITY_TYPE_WEIGHTS, k=1)[0]

        # Activity date bounded by agent tenure
        act_start = max(DATA_START, agent["Hire_Date__c"])
        act_end = min(CURRENT_DATE, agent["Termination_Date__c"] or CURRENT_DATE)
        if act_end <= act_start:
            act_end = act_start + timedelta(days=1)
        activity_dt = fake.date_time_between(start_date=act_start, end_date=act_end)

        if activity_type == "SHOWING":
            duration = random.randint(30, 90)
        elif activity_type == "OPEN_HOUSE":
            duration = random.randint(120, 240)
        elif activity_type == "MEETING":
            duration = random.randint(30, 120)
        elif activity_type == "CALL":
            duration = random.randint(2, 30)
        else:
            duration = None

        outcomes_by_type = {
            "CALL": ["Connected", "Voicemail", "No Answer", "Follow-up scheduled"],
            "EMAIL": ["Sent", "Replied", "Bounced", None],
            "SHOWING": ["Interested", "Not Interested", "Made Offer", None],
            "OPEN_HOUSE": [None, "Lead Captured", "No Leads"],
            "MEETING": ["Action Items", "Next Steps Set", None],
            "TEXT": ["Replied", "Read", "No Reply", None],
        }
        outcome = random.choice(outcomes_by_type[activity_type])

        records.append({
            "Id": f"ACT{i:07d}",
            "Agent_Id__c": agent_id,
            "Contact_Id__c": contact_id,
            "Opportunity_Id__c": opp_id,
            "Activity_Type__c": activity_type,
            "Activity_Date__c": activity_dt,
            "Duration_Minutes__c": duration,
            "Notes__c": fake.sentence(nb_words=8) if random.random() > 0.3 else None,
            "Outcome__c": outcome,
        })
    return pl.DataFrame(records)


def gen_crm_commission_split(
    transactions_df: pl.DataFrame,
    agents_df: pl.DataFrame,
    opportunities_df: pl.DataFrame,
) -> pl.DataFrame:
    """The primary split row goes to the opportunity's OWNER agent, preserving the
    tenure-weighted Pareto signal all the way through to GCI rankings.
    Co-listing (~10% of transactions) adds a secondary row to another active agent."""
    txns = transactions_df.to_dicts()
    agents = {a["Id"]: a for a in agents_df.to_dicts()}
    opps = {o["Id"]: o for o in opportunities_df.to_dicts()}
    active_agent_ids = [a["Id"] for a in agents.values() if a["IsActive__c"]]

    records = []
    seq = 1
    for txn in txns:
        opp = opps[txn["Opportunity_Id__c"]]
        primary_agent_id = opp["Owner_Agent_Id__c"]
        primary_agent = agents[primary_agent_id]
        split_pct = primary_agent["Commission_Split_Pct__c"]
        agent_take = round(txn["Gross_Commission__c"] * split_pct, 2)
        company_take = round(txn["Gross_Commission__c"] * (1 - split_pct), 2)
        payout_dt = txn["Close_Date__c"] + timedelta(days=random.randint(5, 15))
        records.append({
            "Id": f"CSP{seq:06d}",
            "Transaction_Id__c": txn["Id"],
            "Agent_Id__c": primary_agent_id,
            "Split_Pct__c": split_pct,
            "Agent_Take__c": agent_take,
            "Company_Take__c": company_take,
            "Payout_Date__c": payout_dt,
        })
        seq += 1

        # 10% co-list: secondary agent (active only, and not the primary agent)
        if random.random() < 0.10:
            candidates = [a for a in active_agent_ids if a != primary_agent_id]
            if candidates:
                co_agent_id = random.choice(candidates)
                co_agent = agents[co_agent_id]
                co_split = round(agent_take * 0.3, 2)
                co_company_take = round(agent_take * 0.7, 2)
                records.append({
                    "Id": f"CSP{seq:06d}",
                    "Transaction_Id__c": txn["Id"],
                    "Agent_Id__c": co_agent_id,
                    "Split_Pct__c": co_agent["Commission_Split_Pct__c"],
                    "Agent_Take__c": co_split,
                    "Company_Take__c": co_company_take,
                    "Payout_Date__c": payout_dt,
                })
                seq += 1
    return pl.DataFrame(records)


# ============================================================================
# External data generators
# ============================================================================


def _month_iter(start: date, end_exclusive: date):
    cur = start
    while cur < end_exclusive:
        yield cur
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)


def gen_ext_zillow_hvi() -> pl.DataFrame:
    """Monthly ZHVI per zip -- 60 zips x 42 months (2023-01 through 2026-06, inclusive)."""
    records = []
    months = list(_month_iter(date(2023, 1, 1), date(2026, 7, 1)))  # 42 months

    for zip_row in ZIP_CODES:
        market = next(m for m in MARKETS if m["market_id"] == _market_id_for_zip(zip_row["zip_id"]))
        base_zhvi = market["median_price"] * zip_row["price_multiplier"]
        prev_zhvi = None
        zhvi_history = []
        for m_date in months:
            years_elapsed = (m_date - date(2023, 1, 1)).days / 365.25
            trend_factor = 1.04 ** years_elapsed
            seasonal = 1 + 0.01 * math.sin((m_date.month - 1) * math.pi / 6)
            noise = random.gauss(1.0, 0.008)
            zhvi = round(base_zhvi * trend_factor * seasonal * noise / 100) * 100
            mom = None if prev_zhvi is None else round((zhvi - prev_zhvi) / prev_zhvi * 100, 3)
            yoy = None
            if len(zhvi_history) >= 12:
                yoy = round((zhvi - zhvi_history[-12]) / zhvi_history[-12] * 100, 3)
            zhvi_history.append(zhvi)
            records.append({
                "RegionName": zip_row["zip5"],
                "zip_id": zip_row["zip_id"],
                "Date": m_date,
                "ZHVI": zhvi,
                "ZHVI_MoM_Pct": mom,
                "ZHVI_YoY_Pct": yoy,
            })
            prev_zhvi = zhvi
    return pl.DataFrame(records)


def gen_ext_zillow_market_temperature() -> pl.DataFrame:
    records = []
    months = list(_month_iter(date(2023, 1, 1), date(2026, 7, 1)))
    temp_label_map = {"HOT": ["Hot", "Very Hot"], "STABLE": ["Warm", "Neutral"], "COOL": ["Cool", "Cold"]}
    for zip_row in ZIP_CODES:
        for m_date in months:
            base_label = random.choice(temp_label_map[zip_row["temperature"]])
            slr_center = SLR_CENTER[zip_row["temperature"]]
            slr = round(random.gauss(slr_center, 0.015), 4)
            mu, sigma = DOM_PARAMS[zip_row["temperature"]]
            median_dom = max(1, int(random.lognormvariate(mu, sigma)))
            records.append({
                "RegionName": zip_row["zip5"],
                "zip_id": zip_row["zip_id"],
                "Date": m_date,
                "Market_Temperature": base_label,
                "Sale_to_List_Ratio": slr,
                "Median_DOM": median_dom,
            })
    return pl.DataFrame(records)


def gen_ext_freddie_mac_mortgage_rate() -> pl.DataFrame:
    """Weekly 30-year / 15-year fixed mortgage rates, matching real Freddie Mac PMMS history."""
    records = []
    cur = DATA_START
    while cur <= DATA_END:
        rate_30 = mortgage_rate_at(cur)
        rate_15 = round(rate_30 - random.uniform(0.6, 0.9), 3)
        points = round(random.uniform(0.4, 0.9), 2)
        records.append({
            "Week_End_Date": cur,
            "Rate_30Y_Fixed": rate_30,
            "Rate_15Y_Fixed": rate_15,
            "Points_30Y": points,
        })
        cur += timedelta(days=7)
    return pl.DataFrame(records)


def gen_ext_census_demographics() -> pl.DataFrame:
    records = []
    base_pop = {
        1: 873000, 2: 765000, 3: 1936000, 4: 1671000,
        5: 9929000, 6: 3186000, 7: 3299000,
        8: 2269000, 9: 921000, 10: 822000,
        11: 275000, 12: 843000,
    }
    base_income = {
        1: 126000, 2: 137000, 3: 153000, 4: 112000,
        5: 80000, 6: 106000, 7: 96000,
        8: 116000, 9: 95000, 10: 109000,
        11: 95000, 12: 100000,
    }
    for county in COUNTIES:
        for year in [2022, 2023, 2024, 2025]:
            growth = (year - 2022) * 0.005
            pop = int(base_pop[county["county_id"]] * (1 + growth + random.gauss(0, 0.003)))
            income = int(base_income[county["county_id"]] * (1 + growth * 1.5 + random.gauss(0, 0.005)))
            emp_rate = round(random.uniform(0.94, 0.97), 4)
            records.append({
                "county_id": county["county_id"],
                "Year": year,
                "Population": pop,
                "Median_Household_Income": income,
                "Employment_Rate": emp_rate,
            })
    return pl.DataFrame(records)


def gen_ext_walk_score(properties_df: pl.DataFrame) -> pl.DataFrame:
    urban_zips = {"94102", "94103", "94105", "94107", "94110", "94117", "94612",
                  "90017", "90048", "90401", "98101", "98103", "98105", "98109", "98122"}
    records = []
    for prop in properties_df.to_dicts():
        zip_row = next(z for z in ZIP_CODES if z["zip_id"] == prop["zip_id"])
        is_urban = zip_row["zip5"] in urban_zips
        if is_urban:
            walk = random.randint(70, 99)
            transit = random.randint(60, 95)
            bike = random.randint(55, 90)
        else:
            walk = random.randint(20, 75)
            transit = random.randint(15, 65)
            bike = random.randint(25, 75)
        records.append({
            "PROPERTY_ID": prop["PROPERTY_ID"],
            "Walk_Score": walk,
            "Transit_Score": transit,
            "Bike_Score": bike,
            "Score_Date": fake.date_between(start_date=DATA_START, end_date=CURRENT_DATE),
        })
    return pl.DataFrame(records)


# ============================================================================
# Orchestration
# ============================================================================


TSV_ORDER: list[tuple[str, str]] = [
    ("01_geo_market.tsv", "geo_market"),
    ("02_geo_county.tsv", "geo_county"),
    ("03_geo_city.tsv", "geo_city"),
    ("04_geo_zip_code.tsv", "geo_zip_code"),
    ("05_crm_office.tsv", "crm_office"),
    ("06_crm_agent.tsv", "crm_agent"),
    ("07_crm_agent_zip_coverage.tsv", "crm_agent_zip_coverage"),
    ("08_crm_contact.tsv", "crm_contact"),
    ("09_mls_property.tsv", "mls_property"),
    ("10_mls_listing.tsv", "mls_listing"),
    ("11_mls_listing_event_history.tsv", "mls_listing_event_history"),
    ("12_mls_sold_transaction.tsv", "mls_sold_transaction"),
    ("13_mls_pending_sale.tsv", "mls_pending_sale"),
    ("14_mls_listing_showing.tsv", "mls_listing_showing"),
    ("15_crm_opportunity.tsv", "crm_opportunity"),
    ("16_crm_transaction.tsv", "crm_transaction"),
    ("17_crm_commission_split.tsv", "crm_commission_split"),
    ("18_crm_agent_activity.tsv", "crm_agent_activity"),
    ("19_ext_zillow_home_value_index.tsv", "ext_zillow_home_value_index"),
    ("20_ext_zillow_market_temperature.tsv", "ext_zillow_market_temperature"),
    ("21_ext_freddie_mac_mortgage_rate.tsv", "ext_freddie_mac_mortgage_rate"),
    ("22_ext_census_demographics.tsv", "ext_census_demographics"),
    ("23_ext_walk_score.tsv", "ext_walk_score"),
]


def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("[1/23] Geo dimensions...")
    gen_geo_market().write_csv(DATA_DIR / "01_geo_market.tsv", separator="\t")
    gen_geo_county().write_csv(DATA_DIR / "02_geo_county.tsv", separator="\t")
    gen_geo_city().write_csv(DATA_DIR / "03_geo_city.tsv", separator="\t")
    gen_geo_zip_code().write_csv(DATA_DIR / "04_geo_zip_code.tsv", separator="\t")

    print("[2/23] CRM office...")
    df_office = gen_crm_office()
    df_office.write_csv(DATA_DIR / "05_crm_office.tsv", separator="\t")

    print(f"[3/23] CRM agent ({N_AGENTS})...")
    df_agent = gen_crm_agent(N_AGENTS, df_office)
    df_agent.write_csv(DATA_DIR / "06_crm_agent.tsv", separator="\t")
    crestline_licenses = df_agent["License_Number__c"].to_list()

    print("[4/23] CRM agent zip coverage...")
    df_azc = gen_crm_agent_zip_coverage(df_agent, target_n=500)
    df_azc.write_csv(DATA_DIR / "07_crm_agent_zip_coverage.tsv", separator="\t")

    print(f"[5/23] CRM contact ({N_CONTACTS})...")
    df_contact = gen_crm_contact(N_CONTACTS, df_agent)
    df_contact.write_csv(DATA_DIR / "08_crm_contact.tsv", separator="\t")

    print(f"[6/23] MLS property ({N_PROPERTIES})...")
    df_property = gen_mls_property(N_PROPERTIES)
    df_property.write_csv(DATA_DIR / "09_mls_property.tsv", separator="\t")

    print(f"[7/23] MLS listing ({N_LISTINGS}) with Crestline coupling...")
    df_listing = gen_mls_listing(N_LISTINGS, df_property, crestline_licenses)
    df_listing.write_csv(DATA_DIR / "10_mls_listing.tsv", separator="\t")

    print(f"[8/23] MLS listing event history (~{N_EVENT_HISTORY})...")
    df_event_hist = gen_mls_listing_event_history(N_EVENT_HISTORY, df_listing)
    df_event_hist.write_csv(DATA_DIR / "11_mls_listing_event_history.tsv", separator="\t")

    print("[9/23] MLS sold transactions...")
    df_sold = gen_mls_sold_transaction(df_listing, df_property, crestline_licenses)
    df_sold.write_csv(DATA_DIR / "12_mls_sold_transaction.tsv", separator="\t")

    print(f"[10/23] MLS pending sales (~{N_PENDING})...")
    df_pending = gen_mls_pending_sale(df_listing, N_PENDING)
    df_pending.write_csv(DATA_DIR / "13_mls_pending_sale.tsv", separator="\t")

    print(f"[11/23] MLS listing showings ({N_SHOWINGS})...")
    df_showing = gen_mls_listing_showing(N_SHOWINGS, df_listing, df_property, df_contact, crestline_licenses)
    df_showing.write_csv(DATA_DIR / "14_mls_listing_showing.tsv", separator="\t")

    print(f"[12/23] CRM opportunities ({N_OPPORTUNITIES})...")
    df_opp = gen_crm_opportunity(N_OPPORTUNITIES, df_contact, df_agent, df_listing)
    df_opp.write_csv(DATA_DIR / "15_crm_opportunity.tsv", separator="\t")

    print(f"[13/23] CRM transactions (target {N_CRM_TRANSACTIONS})...")
    df_txn = gen_crm_transaction(N_CRM_TRANSACTIONS, df_opp, df_sold, df_listing)
    df_txn.write_csv(DATA_DIR / "16_crm_transaction.tsv", separator="\t")

    print("[14/23] CRM commission splits...")
    df_split = gen_crm_commission_split(df_txn, df_agent, df_opp)
    df_split.write_csv(DATA_DIR / "17_crm_commission_split.tsv", separator="\t")

    print(f"[15/23] CRM agent activities ({N_AGENT_ACTIVITIES})...")
    df_activity = gen_crm_agent_activity(N_AGENT_ACTIVITIES, df_agent, df_contact, df_opp)
    df_activity.write_csv(DATA_DIR / "18_crm_agent_activity.tsv", separator="\t")

    print("[16-20/23] External data...")
    gen_ext_zillow_hvi().write_csv(DATA_DIR / "19_ext_zillow_home_value_index.tsv", separator="\t")
    gen_ext_zillow_market_temperature().write_csv(DATA_DIR / "20_ext_zillow_market_temperature.tsv", separator="\t")
    gen_ext_freddie_mac_mortgage_rate().write_csv(DATA_DIR / "21_ext_freddie_mac_mortgage_rate.tsv", separator="\t")
    gen_ext_census_demographics().write_csv(DATA_DIR / "22_ext_census_demographics.tsv", separator="\t")
    gen_ext_walk_score(df_property).write_csv(DATA_DIR / "23_ext_walk_score.tsv", separator="\t")

    print(f"All TSV files written to {DATA_DIR}")


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    table_classes = {
        "geo_market": GeoMarket,
        "geo_county": GeoCounty,
        "geo_city": GeoCity,
        "geo_zip_code": GeoZipCode,
        "crm_office": CrmOffice,
        "crm_agent": CrmAgent,
        "crm_agent_zip_coverage": CrmAgentZipCoverage,
        "crm_contact": CrmContact,
        "mls_property": MlsProperty,
        "mls_listing": MlsListing,
        "mls_listing_event_history": MlsListingEventHistory,
        "mls_sold_transaction": MlsSoldTransaction,
        "mls_pending_sale": MlsPendingSale,
        "mls_listing_showing": MlsListingShowing,
        "crm_opportunity": CrmOpportunity,
        "crm_transaction": CrmTransaction,
        "crm_commission_split": CrmCommissionSplit,
        "crm_agent_activity": CrmAgentActivity,
        "ext_zillow_home_value_index": ExtZillowHomeValueIndex,
        "ext_zillow_market_temperature": ExtZillowMarketTemperature,
        "ext_freddie_mac_mortgage_rate": ExtFreddieMacMortgageRate,
        "ext_census_demographics": ExtCensusDemographics,
        "ext_walk_score": ExtWalkScore,
    }

    for fname, tname in TSV_ORDER:
        cls = table_classes[tname]
        fpath = DATA_DIR / fname
        if not fpath.exists():
            print(f"Skipping missing {fname}")
            continue
        df = pl.read_csv(fpath, separator="\t", infer_schema_length=10000, try_parse_dates=True)
        rows = df.to_dicts()
        if not rows:
            continue
        with Session(engine) as session:
            session.bulk_insert_mappings(cls, rows)
            session.commit()
        print(f"  Loaded {len(rows):>7} rows into {tname}")

    print(f"SQLite database created at {DATABASE_PATH}")


def main() -> None:
    print(f"=== Generating {DATASET_NAME} ===")
    generate_all_tsv()
    create_sqlite_database()
    print("Done.")


if __name__ == "__main__":
    main()
