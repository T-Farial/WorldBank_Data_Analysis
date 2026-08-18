import os
import sys
import matplotlib.pyplot as plt
import pandas as pd
import requests

# Dictionary of available indicators for POINT 1
INDICATOR_OPTIONS = {
    "1": ("NY.GDP.MKTP.CD", "GDP (Current US$)"),
    "2": ("SP.POP.TOTL", "Total Population"),
    "3": ("SE.PRM.CENR.ZS", "Primary School Enrollment (%)"),
    "4": ("SL.UEM.TOTL.ZS", "Unemployment Rate (% of total labor force)"),
    "5": ("EN.ATM.CO2E.PC", "CO2 Emissions (metric tons per capita)"),
}

# ISO-3 Code list for validation in POINT 2
VALID_ISO3_CODES = {
    "AFG", "ALB", "DZA", "AND", "AGO", "ATG", "ARG", "ARM", "AUS", "AUT",
    "AZE", "BHS", "BHR", "BGD", "BRB", "BLR", "BEL", "BLZ", "BEN", "BTN",
    "BOL", "BIH", "BWA", "BRA", "BRN", "BGR", "BFA", "BDI", "KHM", "CMR",
    "CAN", "CPV", "CAF", "TCD", "CHL", "CHN", "COL", "COM", "COG", "CRI",
    "HRV", "CUB", "CYP", "CZE", "DNK", "DJI", "DMA", "DOM", "ECU", "EGY",
    "SLV", "GNQ", "ERI", "EST", "SWZ", "ETH", "FJI", "FIN", "FRA", "GAB",
    "GMB", "GEO", "DEU", "GHA", "GRC", "GRD", "GTM", "GIN", "GNB", "GUY",
    "HTI", "HND", "HUN", "ISL", "IND", "IDN", "IRN", "IRQ", "IRL", "ISR",
    "ITA", "JAM", "JPN", "JOR", "KAZ", "KEN", "KIR", "KOR", "KWT", "KGZ",
    "LAO", "LVA", "LBN", "LSO", "LBR", "LBY", "LIE", "LTU", "LUX", "MDG",
    "MWI", "MYS", "MDV", "MLI", "MLT", "MHL", "MRT", "MUS", "MEX", "FSM",
    "MDA", "MCO", "MNG", "MNE", "MAR", "MOZ", "MMR", "NAM", "NRU", "NPL",
    "NLD", "NZL", "NIC", "NER", "NGA", "MKD", "NOR", "OMN", "PAK", "PLW",
    "PAN", "PNG", "PRY", "PER", "PHL", "POL", "PRT", "QAT", "ROU", "RUS",
    "RWA", "KNA", "LCA", "VCT", "WSM", "SMR", "STP", "SAU", "SEN", "SRB",
    "SYC", "SLE", "SGP", "SVK", "SVN", "SLB", "SOM", "ZAF", "ESP", "LKA",
    "SDN", "SUR", "SWE", "CHE", "SYR", "TWN", "TJK", "TZA", "THA", "TLS",
    "TGO", "TON", "TTO", "TUN", "TUR", "TKM", "TUV", "UGA", "UKR", "ARE",
    "GBR", "USA", "URY", "UZB", "VUT", "VEN", "VNM", "YEM", "ZMB", "ZWE",
}


def fetch_data(
    country_codes: list[str], indicator: str, start_year: int, end_year: int
) -> list[dict]:
    """Fetch raw data from the World Bank API for multiple countries."""
    countries_str = ";".join(country_codes)
    url = f"http://api.worldbank.org/v2/country/{countries_str}/indicator/{indicator}"
    params = {
        "date": f"{start_year}:{end_year}",
        "format": "json",
        "per_page": 10000,
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) < 2:
            raise ValueError(
                "API returned an unexpected response or invalid parameters."
            )

        return data[1]

    except requests.exceptions.Timeout:
        print("Error: The request to World Bank API timed out.")
    except requests.exceptions.HTTPError as err:
        print(f"Error: HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"Error: Unable to connect to API ({err}).")
    except ValueError as err:
        print(f"Error: {err}")

    return []


def parse_api_response(raw_data: list[dict]) -> pd.DataFrame:
    """Extract required fields from raw JSON response into a Pandas DataFrame."""
    if not raw_data:
        print("Error: Empty dataset received.")
        return pd.DataFrame()

    records = []
    for item in raw_data:
        records.append(
            {
                "country": item.get("country", {}).get("value"),
                "country_code": item.get("countryiso3code"),
                "year": item.get("date"),
                "value": item.get("value"),
            }
        )

    return pd.DataFrame(records)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean data by removing nulls, converting types, and dropping duplicates."""
    if df.empty:
        return df

    df = df.dropna(subset=["country", "year", "value"]).copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["year", "value"])
    df["year"] = df["year"].astype(int)
    df = df.drop_duplicates(subset=["country_code", "year"])
    df = df.sort_values(by=["country", "year"]).reset_index(drop=True)
    return df


def validate_data(df: pd.DataFrame, expected_countries: list[str]) -> bool:
    """Validate completeness and non-emptiness of dataset."""
    if df.empty:
        print("Validation Error: Dataset is empty after cleaning.")
        return False

    retrieved_codes = set(df["country_code"].unique())
    missing = [c for c in expected_countries if c.upper() not in retrieved_codes]

    if missing:
        print(f"Warning: Missing or no data available for code(s): {', '.join(missing)}")

    return True


def analyze_data(df: pd.DataFrame) -> dict:
    """Perform analysis: Min/Max, Trend Over Time, and Comparison."""
    if df.empty:
        return {}

    analysis = {}
    max_idx = df["value"].idxmax()
    min_idx = df["value"].idxmin()
    analysis["highest_overall"] = df.loc[max_idx].to_dict()
    analysis["lowest_overall"] = df.loc[min_idx].to_dict()

    trends = {}
    for country, group in df.groupby("country"):
        group = group.sort_values("year")
        if len(group) < 2:
            trends[country] = "Not enough data to calculate trend."
            continue

        first_val = group.iloc[0]["value"]
        last_val = group.iloc[-1]["value"]
        first_yr = group.iloc[0]["year"]
        last_yr = group.iloc[-1]["year"]

        if first_val == 0:
            pct_change = None
        else:
            pct_change = ((last_val - first_val) / abs(first_val)) * 100

        trends[country] = {
            "start_year": first_yr,
            "end_year": last_yr,
            "start_value": first_val,
            "end_value": last_val,
            "pct_change": pct_change,
        }

    analysis["trends"] = trends
    return analysis


def create_visualizations(
    df: pd.DataFrame, indicator_name: str, output_dir: str = "output"
):
    """Generate 4 dashboard subplots for multi-country analysis."""
    if df.empty:
        print("Error: Cannot create chart. Dataset is empty.")
        return

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as err:
        print(f"Error: Cannot create output directory: {err}")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"World Bank Dashboard: {indicator_name}", fontsize=16, fontweight="bold"
    )

    # 1. Line Chart
    for country, group in df.groupby("country"):
        axes[0, 0].plot(
            group["year"], group["value"], marker="o", label=country, linewidth=2
        )
    axes[0, 0].set_title("1. Indicator Change Over Time")
    axes[0, 0].set_xlabel("Year")
    axes[0, 0].set_ylabel("Value")
    axes[0, 0].legend()
    axes[0, 0].grid(True, linestyle="--", alpha=0.6)

    # 2. Bar Chart (Latest Year)
    latest_df = df.sort_values("year").groupby("country").last().reset_index()
    axes[0, 1].bar(
        latest_df["country"], latest_df["value"], color="skyblue", edgecolor="black"
    )
    axes[0, 1].set_title(
        f"2. Country Comparison (Latest Year: {latest_df['year'].max()})"
    )
    axes[0, 1].set_ylabel("Value")
    axes[0, 1].grid(axis="y", linestyle="--", alpha=0.6)

    # 3. Bar Chart (Min vs Max)
    countries = df["country"].unique()
    x = range(len(countries))
    width = 0.35
    mins = [df[df["country"] == c]["value"].min() for c in countries]
    maxs = [df[df["country"] == c]["value"].max() for c in countries]

    axes[1, 0].bar(
        [p - width / 2 for p in x],
        mins,
        width,
        label="Lowest Value",
        color="salmon",
    )
    axes[1, 0].bar(
        [p + width / 2 for p in x],
        maxs,
        width,
        label="Highest Value",
        color="teal",
    )
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(countries)
    axes[1, 0].set_title("3. Highest vs Lowest Historical Values")
    axes[1, 0].set_ylabel("Value")
    axes[1, 0].legend()
    axes[1, 0].grid(axis="y", linestyle="--", alpha=0.6)

    # 4. Box Plot
    data_by_country = [group["value"].dropna() for _, group in df.groupby("country")]
    labels = list(df.groupby("country").groups.keys())
    axes[1, 1].boxplot(data_by_country, tick_labels=labels)
    axes[1, 1].set_title("4. Value Distribution & Variance")
    axes[1, 1].set_ylabel("Value")
    axes[1, 1].grid(True, linestyle="--", alpha=0.6)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    filepath = os.path.join(output_dir, "dashboard_visualizations.png")
    try:
        plt.savefig(filepath, dpi=300)
        print(f"\nDashboard chart successfully saved to '{filepath}'.")
        plt.show()
    except Exception as err:
        print(f"Error: Cannot create chart file: {err}")


def save_data(df: pd.DataFrame, output_dir: str = "output"):
    """Export clean processed dataset to CSV."""
    if df.empty:
        print("Warning: Skipping file save because dataset is empty.")
        return

    try:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "cleaned_worldbank_data.csv")
        df.to_csv(filepath, index=False)
        print(f"Cleaned dataset successfully saved to '{filepath}'.")
    except Exception as err:
        print(f"Error: Cant save CSV file ({err}).")


# ==========================================
# INPUT VALIDATION FUNCTIONS
# ==========================================

def get_user_indicator() -> tuple[str, str]:
    """POINT 1: Display numbered choices and select indicator."""
    print("\nAvailable Indicators:")
    for num, (code, title) in INDICATOR_OPTIONS.items():
        print(f"  {num}. {code} ({title})")

    while True:
        choice = input("\nChoose an indicator (1-5) [default: 1]: ").strip() or "1"
        if choice in INDICATOR_OPTIONS:
            return INDICATOR_OPTIONS[choice]
        print("Error: Invalid choice. Please enter a number between 1 and 5.")


def get_user_countries() -> list[str]:
    """POINT 2: Validate ISO-3 codes, length (2-5), and duplicates."""
    while True:
        user_input = input(
            "\nEnter 2 to 5 ISO Country Codes (comma-separated, e.g. USA, CHN, DEU) [default: USA, CHN, DEU, IND]: "
        ).strip() or "USA, CHN, DEU, IND"

        # Split and clean
        raw_codes = [c.strip().upper() for c in user_input.split(",") if c.strip()]

        # Check for duplicates
        if len(raw_codes) != len(set(raw_codes)):
            print("Error: Duplicate country codes detected. Please provide unique codes.")
            continue

        # Check quantity parameters (2 to 5)
        if len(raw_codes) < 2 or len(raw_codes) > 5:
            print(f"Error: You must enter between 2 and 5 country codes. You entered {len(raw_codes)}.")
            continue

        # Check for valid ISO-3 codes
        invalid_codes = [code for code in raw_codes if code not in VALID_ISO3_CODES]
        if invalid_codes:
            print(f"Error: Invalid 3-letter ISO country code(s): {', '.join(invalid_codes)}.")
            print("Please use standard 3-letter codes (e.g., USA, JPN, DEU, CHN, GBR).")
            continue

        return raw_codes


def get_user_years() -> tuple[int, int]:
    """POINT 3: Validate start/end years within allowed parameters (1960 - 2024)."""
    min_year = 1960
    max_year = 2024

    print(f"\nYear Range Parameters:")
    print(f" - Allowed Years: {min_year} to {max_year}")
    print(" - Start Year must be less than or equal to End Year.")

    while True:
        try:
            start_str = input(f"\nEnter Start Year [{min_year}-{max_year}] [default: 2010]: ").strip() or "2010"
            end_str = input(f"Enter End Year [{min_year}-{max_year}] [default: 2023]: ").strip() or "2023"

            start_year = int(start_str)
            end_year = int(end_str)

            if start_year < min_year or start_year > max_year:
                print(f"Error: Start year must be between {min_year} and {max_year}.")
                continue

            if end_year < min_year or end_year > max_year:
                print(f"Error: End year must be between {min_year} and {max_year}.")
                continue

            if start_year > end_year:
                print("Error: Start year cannot be greater than end year.")
                continue

            return start_year, end_year

        except ValueError:
            print("Error: Years must be numeric integers.")


def main():
    print("=" * 60)
    print("      WORLD BANK DATA ANALYSIS DASHBOARD BUILDER       ")
    print("=" * 60)

    # 1. Indicator Selection
    indicator_code, indicator_title = get_user_indicator()

    # 2. Country Codes Selection
    country_codes = get_user_countries()

    # 3. Year Parameters Selection
    start_year, end_year = get_user_years()

    # Execution Pipeline
    print("\nFetching data from World Bank API...")
    raw_data = fetch_data(country_codes, indicator_code, start_year, end_year)

    print("Parsing API response...")
    df_raw = parse_api_response(raw_data)

    print("Cleaning dataset...")
    df_clean = clean_data(df_raw)

    if not validate_data(df_clean, country_codes):
        print("\nProcess halted due to failed data validation.")
        return

    print("Analyzing data...")
    results = analyze_data(df_clean)

    # Display Results
    print("\n" + "=" * 40)
    print("           ANALYSIS REPORT           ")
    print("=" * 40)

    high = results.get("highest_overall", {})
    low = results.get("lowest_overall", {})
    print(
        f"\nHighest Single Record: {high.get('country')} ({high.get('year')}): {high.get('value'):,.2f}"
    )
    print(
        f"Lowest Single Record:  {low.get('country')} ({low.get('year')}): {low.get('value'):,.2f}"
    )

    print("\nTrend Summary:")
    for country, info in results.get("trends", {}).items():
        if isinstance(info, str):
            print(f" - {country}: {info}")
        else:
            pct_str = (
                f"{info['pct_change']:+.2f}%"
                if info["pct_change"] is not None
                else "N/A"
            )
            print(
                f" - {country} ({info['start_year']} -> {info['end_year']}): "
                f"{info['start_value']:,.2f} to {info['end_value']:,.2f} (Change: {pct_str})"
            )

    # Export & Visualize
    save_data(df_clean)
    create_visualizations(df_clean, indicator_title)


if __name__ == "__main__":
    main()