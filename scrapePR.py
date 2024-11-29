from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

# Set up Chrome options
options = webdriver.ChromeOptions()
options.add_argument("--disable-extensions")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

save_folder = "articles_PRNewsWire"
os.makedirs(save_folder, exist_ok=True)

# Starting URL
base_url = "https://www.prnewswire.com/news-releases/news-releases-list/"
current_page_file = "current_page_count.txt"
progress_file = "progress.json"

month = "10"
year = "2024"
hour = "17"
day = "01"


# Load the current page count or start from the first page
if os.path.exists(current_page_file):
    with open(current_page_file, 'r') as f:
        current_count = int(f.read().strip())
else:
    current_count = 102  # Start from the first page

# Load progress from the previous run, if it exists
if os.path.exists(progress_file):
    with open(progress_file, 'r') as f:
        progress = json.load(f)
        processed_links = progress.get('links', [])
else:
    processed_links = []

keywords = ['venture', 'VC', 'series', 'round', 'valuation', 'unicorn']
keyword_pattern = re.compile(r'|'.join(keywords), re.IGNORECASE)

def fetch_article_details(link):
    """Fetch article details and save it if it matches the keyword criteria. Save failed links."""
    try:
        driver.get(link)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "mm-0")))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        wrap = soup.find('div', id="mm-0")
        if wrap:
            page_wrap = wrap.find('div', class_="page-wrap")
            if page_wrap:
                main_content = page_wrap.find('main', id="main").find("article", class_="news-release inline-gallery-template")
                if not main_content:
                    main_content = page_wrap.find('main', id="main").find("article", class_="news-release static-gallery-template")

                if main_content:
                    if (current_count == 102):
                        found_header_and_container = main_content.find('header', class_='container release-header')
                        third_row = found_header_and_container.find_all('div', class_='row')[3]
                        #print(f"FOUND THIRD ROW: {third_row}")
                        date = third_row.find("div", class_="col-lg-8 col-md-8 col-sm-7 swaping-class-left").find("p", class_="mb-no").get_text()
                        #print(f"ARTICLE DATE: {date}")
                        dt = datetime.strptime(date.replace(" ET", ""), "%b %d, %Y, %H:%M")

                        dt_plus_one_hour = dt + timedelta(hours=1)

                        month = dt_plus_one_hour.strftime("%m") 
                        day = dt_plus_one_hour.strftime("%d")   
                        year = dt_plus_one_hour.strftime("%Y")  
                        hour = dt_plus_one_hour.strftime("%H") 


                        #print(f"Month: {month}, Day: {day}, Year: {year}, Hour: {hour}")



                    for script in main_content(['script', 'style']):
                        script.decompose()

                    formatted_text = main_content.get_text(separator='\n', strip=True)
                    found_keywords = keyword_pattern.findall(formatted_text)

                    if len(found_keywords) >= 2:
                        title = link.split('/')[-1]  # Fallback title (can be adjusted)
                        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)  # Remove invalid characters
                        file_path = os.path.join(save_folder, f"{safe_title}.txt")

                        # Try saving the article
                        try:
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(formatted_text)
                            print(f"Saved article: {safe_title}")
                            return link  # Return the link if the article was saved successfully
                        except Exception as e:
                            print(f"Failed to save {safe_title}: {e}")
                            append_failed_link(link)
                            return None
                else:
                    print(f"Main content not found for article at {link}. Skipping...")
                    append_failed_link(link)
                    return None
            else:
                print(f"Page wrapper not found for {link}. Skipping...")
                append_failed_link(link)
                return None
        else:
            print(f"Wrap element not found for {link}. Skipping...")
            append_failed_link(link)
            return None
    except Exception as e:
        print(f"Error fetching article from {link}: {e}")
        append_failed_link(link)
        return None

def append_failed_link(link):
    """Append failed link to the failed links file."""
    with open('failed_links.txt', 'a') as f:
        f.write(link + '\n')

def scrape_page(current_count):
    """Scrape a single page of articles and return article links."""
    if (current_count == 103):
        current_count = 1
        paging_link = f"{base_url}?page={current_count}&pagesize=100&month={month}&day={day}&year={year}&hour={hour}"

    else:
        paging_link = f"{base_url}?page={current_count}&pagesize=100&month={month}&day={day}&year={year}&hour={hour}"
    driver.get(paging_link)
    print(f"Visiting page: {paging_link}")

    WebDriverWait(driver, 50).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".prncom.prncom_news-releases.prncom_news-releases_headline-listing"))
    )

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    press_releases = soup.find_all('div', class_='row newsCards', lang=True)

    article_links = []
    for release in press_releases:
        try:
            div_card = release.find('div', class_=['col-sm-12', 'card col-view'])
            link = div_card.find('a', class_='newsreleaseconsolidatelink display-outline w-100').get('href')

            if link not in processed_links:  # Duplicate check
                article_links.append(link)
        except Exception as e:
            print(f"Error processing release: {e}")

    return article_links

def save_progress():
    """Save progress to a file."""
    with open(progress_file, 'w') as f:
        json.dump({'links': processed_links}, f)

def main():
    global processed_links, current_count

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:  # Adjust workers based on system capacity
            while True:
                article_links = scrape_page(current_count)

                if not article_links:
                    print("No more articles found.")
                    break

                # Process articles in parallel
                results = list(executor.map(fetch_article_details, article_links))

                # Filter out None values (failed fetches) and add successful links to processed_links
                processed_links.extend([link for link in results if link])

                # Save progress every 10 pages (adjust as needed)
                if current_count % 10 == 0:
                    save_progress()

                current_count += 1
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
