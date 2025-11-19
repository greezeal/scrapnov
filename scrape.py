import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from urllib.parse import urljoin, urlparse, urlencode
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LightNovelScraper:
    def __init__(self, base_url="https://lightnovelpub.org"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create directories
        os.makedirs('data/novels', exist_ok=True)
    
    def get_current_timestamp(self):
        """Get current timestamp in ISO format"""
        return datetime.now().isoformat()
    
    def build_novel_list_url(self, page=1, status="completed", order="popular"):
        """Build URL for novel list with pagination"""
        params = {
            'page': page,
            'order': order,
            'status': status
        }
        return f"{self.base_url}/genre-all/?{urlencode(params)}"
    
    def get_novel_list_paginated(self, start_page=1, max_pages=1, status="completed", order="popular"):
        """Get novel list with pagination support"""
        novels = []
        current_page = start_page
        
        logger.info(f"📖 Fetching novel list from page {start_page} to {max_pages}")
        
        while current_page <= max_pages:
            url = self.build_novel_list_url(current_page, status, order)
            logger.info(f"📄 Processing page {current_page}/{max_pages}")
            
            try:
                response = self.session.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract novels from current page
                page_novels = self.extract_novels_from_page(soup)
                if not page_novels:
                    logger.warning(f"❌ No novels found on page {current_page}")
                    break
                
                novels.extend(page_novels)
                logger.info(f"✅ Page {current_page}: Found {len(page_novels)} novels (Total: {len(novels)})")
                
                current_page += 1
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Error fetching novel list page {current_page}: {e}")
                break
        
        logger.info(f"🎉 Finished fetching novels. Total: {len(novels)} novels")
        return novels
    
    def extract_novels_from_page(self, soup):
        """Extract novels from a single page"""
        novels = []
        novel_cards = soup.select('.recommendation-card')
        
        for card in novel_cards:
            try:
                novel = self.extract_novel_info(card)
                if novel:
                    novel['scraped_at'] = self.get_current_timestamp()
                    novels.append(novel)
            except Exception as e:
                logger.error(f"Error extracting novel info from card: {e}")
                continue
        
        return novels
    
    def extract_novel_info(self, card):
        """Extract novel information from card element"""
        try:
            title_link = card.select_one('.card-title')
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            
            novel_link = card.select_one('a.card-cover-link')
            if novel_link and 'href' in novel_link.attrs:
                novel_path = novel_link['href']
                slug = novel_path.strip('/').split('/')[-1]
            else:
                slug = self.slugify(title)
            
            cover_img = card.select_one('.card-cover img')
            cover_url = cover_img['src'] if cover_img and 'src' in cover_img.attrs else None
            if cover_url and not cover_url.startswith('http'):
                cover_url = urljoin(self.base_url, cover_url)
            
            rating_elem = card.select_one('.card-rating')
            rating = None
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r'★\s*([\d.]+)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))
            
            chapters_elem = card.select_one('.chapters')
            chapters_count = None
            if chapters_elem:
                chapters_text = chapters_elem.get_text(strip=True)
                chapters_match = re.search(r'(\d+)\s*chapters', chapters_text)
                if chapters_match:
                    chapters_count = int(chapters_match.group(1))
            
            rank_elem = card.select_one('.card-rank')
            rank = None
            if rank_elem:
                rank_text = rank_elem.get_text(strip=True)
                rank_match = re.search(r'RANK\s*(\d+)', rank_text)
                if rank_match:
                    rank = int(rank_match.group(1))
            
            novel_info = {
                'id': slug,
                'slug': slug,
                'title': title,
                'cover_url': cover_url,
                'rating': rating,
                'chapters_count': chapters_count,
                'rank': rank,
                'url': urljoin(self.base_url, novel_path) if novel_link else None,
                'first_scraped': self.get_current_timestamp(),
                'last_updated': self.get_current_timestamp()
            }
            
            return novel_info
            
        except Exception as e:
            logger.error(f"Error extracting novel info: {e}")
            return None
    
    def get_novel_detail(self, novel_slug):
        """Get detailed information for a specific novel"""
        url = f"{self.base_url}/novel/{novel_slug}/"
        logger.info(f"🔍 Fetching novel details: {novel_slug}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            detail_info = self.extract_novel_detail(soup, novel_slug)
            if detail_info:
                detail_info['last_updated'] = self.get_current_timestamp()
                detail_info['scraped_at'] = self.get_current_timestamp()
            return detail_info
            
        except Exception as e:
            logger.error(f"❌ Error fetching novel details for {novel_slug}: {e}")
            return None
    
    def extract_novel_detail(self, soup, novel_slug):
        """Extract detailed novel information"""
        try:
            title_elem = soup.select_one('.novel-title')
            title = title_elem.get_text(strip=True) if title_elem else None
            
            author_elem = soup.select_one('.novel-author')
            author = None
            if author_elem:
                author_text = author_elem.get_text(strip=True)
                author_match = re.search(r'Author:\s*(.+)', author_text)
                if author_match:
                    author = author_match.group(1)
            
            cover_elem = soup.select_one('.novel-cover')
            cover_url = cover_elem['src'] if cover_elem and 'src' in cover_elem.attrs else None
            if cover_url and not cover_url.startswith('http'):
                cover_url = urljoin(self.base_url, cover_url)
            
            stats = {}
            stat_boxes = soup.select('.stat-box')
            for stat in stat_boxes:
                label_elem = stat.select_one('.stat-label')
                value_elem = stat.select_one('.stat-value')
                if label_elem and value_elem:
                    label = label_elem.get_text(strip=True).lower()
                    value = value_elem.get_text(strip=True)
                    stats[label] = value
            
            status_elem = soup.select_one('.status-badge')
            status = status_elem.get_text(strip=True) if status_elem else None
            
            genres = []
            genre_tags = soup.select('.genre-tag')
            for tag in genre_tags:
                genres.append(tag.get_text(strip=True))
            
            summary_elem = soup.select_one('.summary-content')
            summary = summary_elem.get_text(strip=True) if summary_elem else None
            
            rating = None
            rank = None
            
            rating_elem = soup.select_one('.card-rating')
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r'★\s*([\d.]+)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))
            
            rank_elem = soup.select_one('.rank-badge')
            if rank_elem:
                rank_text = rank_elem.get_text(strip=True)
                rank_match = re.search(r'RANK\s*(\d+)', rank_text)
                if rank_match:
                    rank = int(rank_match.group(1))
            
            detail_info = {
                'id': novel_slug,
                'slug': novel_slug,
                'title': title,
                'author': author,
                'cover_url': cover_url,
                'rating': rating,
                'rank': rank,
                'status': status,
                'genres': genres,
                'summary': summary,
                'stats': stats,
                'url': f"{self.base_url}/novel/{novel_slug}/"
            }
            
            return detail_info
            
        except Exception as e:
            logger.error(f"Error extracting novel details: {e}")
            return None
    
    def get_all_chapters_for_novel(self, novel_slug, existing_data=None):
        """Get ALL chapters for a novel with content - WITH DIRECT SAVING"""
        all_new_chapters = []
        page = 1
        
        logger.info(f"📚 Fetching ALL chapters for novel: {novel_slug}")
        
        # Get existing chapters for merging
        existing_chapters = []
        if existing_data and 'chapters' in existing_data:
            existing_chapters = existing_data['chapters']
            logger.info(f"Found {len(existing_chapters)} existing chapters")
        
        # Collect ALL chapter URLs first
        all_chapter_urls = []
        
        while True:
            url = f"{self.base_url}/novel/{novel_slug}/chapters/"
            if page > 1:
                url += f"?page={page}"
            
            try:
                logger.info(f"Fetching chapters page {page} for {novel_slug}")
                response = self.session.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                page_chapters = self.extract_chapters_from_page(soup, novel_slug)
                if not page_chapters:
                    logger.info(f"No chapters found on page {page}, stopping")
                    break
                
                for chapter in page_chapters:
                    if not self.is_chapter_exists(existing_chapters, chapter):
                        all_chapter_urls.append(chapter)
                
                logger.info(f"Page {page}: Found {len(page_chapters)} chapters ({len(all_chapter_urls)} new total)")
                
                next_links = soup.select('.page-link[title="Next Page"]')
                has_next_page = any('Next' in link.get_text() or '›' in link.get_text() for link in next_links)
                
                if not has_next_page:
                    logger.info("No next page found, stopping")
                    break
                
                page += 1
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error fetching chapters page {page} for {novel_slug}: {e}")
                break
        
        logger.info(f"🎯 Starting to process {len(all_chapter_urls)} new chapters for {novel_slug}")
        
        # Process chapters and save directly to file
        processed_count = 0
        for i, chapter in enumerate(all_chapter_urls, 1):
            chapter_number = chapter.get('number', 'Unknown')
            
            logger.info(f"📖 Processing chapter {i}/{len(all_chapter_urls)}: {chapter_number}")
            
            try:
                chapter['scraped_at'] = self.get_current_timestamp()
                
                if chapter.get('url'):
                    content = self.get_chapter_content_with_retry(chapter['url'], max_retries=3)
                    chapter['content'] = content
                    chapter['content_scraped_at'] = self.get_current_timestamp()
                    
                    if content:
                        logger.info(f"✅ Successfully processed chapter {chapter_number}")
                    else:
                        logger.warning(f"⚠️ No content for chapter {chapter_number}")
                        chapter['content'] = None
                        chapter['error'] = "Failed to fetch content"
                else:
                    logger.warning(f"⚠️ No URL for chapter {chapter_number}")
                    chapter['content'] = None
                    chapter['error'] = "No chapter URL available"
                
                all_new_chapters.append(chapter)
                processed_count += 1
                
                # ✅ DIRECT SAVE: Save to file every 10 chapters or when significant progress
                if processed_count % 10 == 0 or processed_count == len(all_chapter_urls):
                    self.save_partial_novel_data(novel_slug, existing_data, all_new_chapters, processed_count, i)
                
            except Exception as e:
                logger.error(f"❌ Unexpected error processing chapter {chapter_number}: {e}")
                chapter['content'] = None
                chapter['error'] = f"Unexpected error: {str(e)}"
                chapter['scraped_at'] = self.get_current_timestamp()
                all_new_chapters.append(chapter)
                processed_count += 1
            
            if i < len(all_chapter_urls):
                time.sleep(1)
        
        # Final merge and save
        final_chapters = self.merge_chapters(existing_chapters, all_new_chapters)
        final_chapters = self.sort_chapters(final_chapters)
        
        logger.info(f"📊 Final summary for {novel_slug}: {len(final_chapters)} total chapters")
        return final_chapters
    
    def save_partial_novel_data(self, novel_slug, existing_data, new_chapters, processed_count, current_index):
        """Save partial novel data directly to file"""
        try:
            # Merge current progress
            existing_chapters = existing_data.get('chapters', []) if existing_data else []
            current_merged = self.merge_chapters(existing_chapters, new_chapters)
            
            # Get novel info from existing data or create basic one
            novel_info = existing_data.get('novel_info', {}) if existing_data else {'slug': novel_slug}
            
            # Create partial data structure
            partial_data = {
                'metadata': {
                    'scraped_at': self.get_current_timestamp(),
                    'total_chapters': len(current_merged),
                    'novel_slug': novel_slug,
                    'current_progress': f"{current_index} chapters processed",
                    'is_partial_save': True
                },
                'novel_info': novel_info,
                'chapters': current_merged
            }
            
            filename = f'data/novels/{novel_slug}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(partial_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 DIRECT SAVE: {novel_slug} - {len(current_merged)} chapters ({processed_count}/{current_index} processed)")
            
        except Exception as e:
            logger.error(f"❌ Error in partial save: {e}")
    
    def extract_chapters_from_page(self, soup, novel_slug):
        """Extract chapters from a single page"""
        chapters = []
        chapter_cards = soup.select('.chapter-card')
        
        for card in chapter_cards:
            try:
                chapter = self.extract_chapter_info(card, novel_slug)
                if chapter:
                    chapters.append(chapter)
            except Exception as e:
                logger.error(f"Error extracting chapter info from card: {e}")
                continue
        
        return chapters
    
    def extract_chapter_info(self, card, novel_slug):
        """Extract chapter information from card element"""
        try:
            number_elem = card.select_one('.chapter-number')
            chapter_number = number_elem.get_text(strip=True) if number_elem else None
            
            title_elem = card.select_one('.chapter-title')
            chapter_title = title_elem.get_text(strip=True) if title_elem else None
            
            if 'onclick' in card.attrs:
                onclick_attr = card['onclick']
                url_match = re.search(r"location\.href='([^']+)'", onclick_attr)
                if url_match:
                    chapter_url = url_match.group(1)
                else:
                    link_elem = card.find('a')
                    chapter_url = link_elem['href'] if link_elem and 'href' in link_elem.attrs else None
            else:
                link_elem = card.find('a')
                chapter_url = link_elem['href'] if link_elem and 'href' in link_elem.attrs else None
            
            if chapter_url and not chapter_url.startswith('http'):
                chapter_url = urljoin(self.base_url, chapter_url)
            
            chapter_id = None
            if chapter_url:
                path_parts = urlparse(chapter_url).path.strip('/').split('/')
                if len(path_parts) >= 3 and path_parts[-2] == 'chapter':
                    chapter_id = path_parts[-1]
            
            time_elem = card.select_one('.chapter-time')
            original_time = time_elem.get_text(strip=True) if time_elem else None
            
            chapter_info = {
                'id': chapter_id,
                'number': chapter_number,
                'title': chapter_title,
                'url': chapter_url,
                'original_time': original_time,
                'novel_slug': novel_slug,
                'content': None,
                'scraped_at': None,
                'content_scraped_at': None,
                'error': None
            }
            
            return chapter_info
            
        except Exception as e:
            logger.error(f"Error extracting chapter info from card: {e}")
            return None
    
    def get_chapter_content_with_retry(self, chapter_url, max_retries=3, delay=2):
        """Get chapter content with retry mechanism"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries}")
                
                response = self.session.get(chapter_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                content_elem = soup.select_one('.chapter-text')
                if content_elem:
                    for script in content_elem(["script", "style"]):
                        script.decompose()
                    
                    content = content_elem.get_text(separator='\n', strip=True)
                    if content and len(content.strip()) > 10:
                        return content
                    else:
                        logger.warning(f"Content too short for: {chapter_url}")
                else:
                    logger.warning(f"No content element found for: {chapter_url}")
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = delay * (attempt + 1)
                    time.sleep(wait_time)
                else:
                    logger.error(f"All attempts failed for {chapter_url}")
        
        return None
    
    def sort_chapters(self, chapters):
        """Sort chapters by number in natural order"""
        def chapter_key(chapter):
            number = chapter.get('number', '0')
            try:
                return float(number)
            except (ValueError, TypeError):
                numbers = re.findall(r'\d+\.?\d*', number)
                if numbers:
                    return float(numbers[0])
                return float('inf')
        
        return sorted(chapters, key=chapter_key)
    
    def is_chapter_exists(self, existing_chapters, new_chapter):
        """Check if chapter already exists in existing data"""
        for existing_chapter in existing_chapters:
            if (existing_chapter.get('id') == new_chapter.get('id') or 
                (existing_chapter.get('number') == new_chapter.get('number') and 
                 existing_chapter.get('title') == new_chapter.get('title'))):
                return True
        return False
    
    def merge_chapters(self, existing_chapters, new_chapters):
        """Merge existing chapters with new chapters, avoiding duplicates"""
        merged_chapters = existing_chapters.copy()
        existing_ids = {chap.get('id') for chap in existing_chapters if chap.get('id')}
        existing_numbers = {chap.get('number') for chap in existing_chapters if chap.get('number')}
        
        for new_chapter in new_chapters:
            if (new_chapter.get('id') in existing_ids or 
                new_chapter.get('number') in existing_numbers):
                continue
            
            merged_chapters.append(new_chapter)
        
        return merged_chapters
    
    def load_existing_novel(self, novel_slug):
        """Load existing novel data if available"""
        filename = f'data/novels/{novel_slug}.json'
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading existing novel {novel_slug}: {e}")
        return None
    
    def load_existing_novels_list(self):
        """Load existing novels list"""
        filename = 'data/novels.json'
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading existing novels list: {e}")
        return []
    
    def update_novel_in_list(self, novels_list, updated_novel):
        """Update novel in the novels list, or add if not exists"""
        novel_slug = updated_novel.get('slug')
        
        for i, novel in enumerate(novels_list):
            if novel.get('slug') == novel_slug:
                novels_list[i] = updated_novel
                logger.info(f"🔄 Updated novel in list: {updated_novel['title']}")
                return novels_list
        
        novels_list.append(updated_novel)
        logger.info(f"➕ Added new novel to list: {updated_novel['title']}")
        return novels_list
    
    def save_novels_to_json(self, novels, filename='data/novels.json'):
        """Save novels list to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(novels, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 Saved novels list: {len(novels)} novels")
        except Exception as e:
            logger.error(f"❌ Error saving novels to JSON: {e}")
    
    def save_complete_novel_to_json(self, novel_data, chapters_with_content, filename=None):
        """Save complete novel data with chapters and content to JSON file"""
        if filename is None:
            filename = f'data/novels/{novel_data["slug"]}.json'
        
        try:
            complete_data = {
                'metadata': {
                    'scraped_at': self.get_current_timestamp(),
                    'total_chapters': len(chapters_with_content),
                    'novel_slug': novel_data['slug'],
                    'novel_title': novel_data['title'],
                    'first_scraped': novel_data.get('first_scraped', self.get_current_timestamp()),
                    'last_updated': self.get_current_timestamp(),
                    'is_complete': True
                },
                'novel_info': novel_data,
                'chapters': chapters_with_content
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(complete_data, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 FINAL SAVE: {filename} ({len(chapters_with_content)} chapters)")
            
        except Exception as e:
            logger.error(f"❌ Error saving complete novel to JSON: {e}")
    
    def slugify(self, text):
        """Convert text to URL-friendly slug"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text
    
    def scrape_all_novels_complete(self, start_page=1, max_pages=1):
        """MAIN METHOD: Scrape ALL novels with ALL chapters - IMPROVED SAVING"""
        logger.info(f"🚀 STARTING COMPLETE SCRAPING: Pages {start_page} to {max_pages}")
        
        # Step 1: Get novel list from website
        novels = self.get_novel_list_paginated(
            start_page=start_page,
            max_pages=max_pages,
            status="completed",
            order="popular"
        )
        
        if not novels:
            logger.error("❌ No novels found! Exiting.")
            return []
        
        logger.info(f"📚 Found {len(novels)} novels to process")
        
        # Step 2: Load existing data
        existing_novels_list = self.load_existing_novels_list()
        updated_novels_list = existing_novels_list.copy()
        
        # Step 3: FIRST PASS - Get novel details and SAVE to novels.json
        logger.info("🎯 STEP 1: Getting novel details and saving to novels.json")
        
        novel_details_list = []
        for i, novel in enumerate(novels, 1):
            novel_slug = novel['slug']
            novel_title = novel['title']
            
            logger.info(f"🔍 Getting details for novel {i}/{len(novels)}: {novel_title}")
            
            # Skip if already exists in list
            if any(n.get('slug') == novel_slug for n in updated_novels_list):
                logger.info(f"⏭️ Novel already in list: {novel_title}")
                continue
            
            # Get detailed novel info
            detail = self.get_novel_detail(novel_slug)
            if detail:
                novel_data = {**novel, **detail}
            else:
                novel_data = novel
            
            novel_details_list.append(novel_data)
            
            # ✅ SAVE 1: Update novels list IMMEDIATELY after getting details
            updated_novels_list = self.update_novel_in_list(updated_novels_list, novel_data)
            self.save_novels_to_json(updated_novels_list)
            
            logger.info(f"✅ Saved novel info: {novel_title}")
            
            # Short delay between novel detail requests
            if i < len(novels):
                time.sleep(2)
        
        logger.info("🎯 STEP 2: Now processing chapters for each novel")
        
        # Step 4: SECOND PASS - Process chapters for each novel
        for i, novel_data in enumerate(novel_details_list, 1):
            novel_slug = novel_data['slug']
            novel_title = novel_data['title']
            
            logger.info(f"📖 Processing chapters for novel {i}/{len(novel_details_list)}: {novel_title}")
            
            # Load existing novel data (if any)
            existing_data = self.load_existing_novel(novel_slug)
            
            # Get ALL chapters
            all_chapters = self.get_all_chapters_for_novel(novel_slug, existing_data)
            
            # ✅ SAVE 2: Save complete novel data with chapters
            self.save_complete_novel_to_json(novel_data, all_chapters)
            
            logger.info(f"✅ COMPLETED: {novel_title} ({len(all_chapters)} chapters)")
            
            # Progress update
            logger.info(f"📊 Overall progress: {i}/{len(novel_details_list)} novels completed")
            
            # Delay between novels
            if i < len(novel_details_list):
                logger.info("⏳ Waiting 5 seconds before next novel...")
                time.sleep(5)
        
        logger.info(f"🎉 SCRAPING COMPLETED! Processed {len(novel_details_list)} novels")
        return updated_novels_list

def main():
    """Main function - Configure your scraping here"""
    scraper = LightNovelScraper()
    
    # CONFIGURATION
    START_PAGE = 1
    MAX_PAGES = 1
    
    print("🚀 Light Novel Scraper - TWO-PASS SAVING")
    print("=========================================")
    print(f"📄 Pages: {START_PAGE} to {MAX_PAGES}")
    print("🎯 Step 1: Save novel details to novels.json")
    print("🎯 Step 2: Process chapters and save to individual files") 
    print("⏰ This may take a while...")
    print()
    
    novels = scraper.scrape_all_novels_complete(
        start_page=START_PAGE,
        max_pages=MAX_PAGES
    )
    
    print()
    print("📊 SCRAPING SUMMARY")
    print("===================")
    print(f"✅ Total novels processed: {len(novels)}")
    print("💾 novels.json: Contains all novel details")
    print("💾 data/novels/: Contains complete novel data with chapters")
    print("🎉 All done!")

if __name__ == "__main__":
    main()