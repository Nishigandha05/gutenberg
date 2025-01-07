import unittest
from unittest.mock import patch, MagicMock
import json
from models import app

class TestGutenbergAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
        # Mock database response
        self.mock_book = {
            'title': 'Sample Book',
            'gutenberg_id': 1,
            'download_count': 1000,
            'author_info': {
                'name': 'Test Author',
                'birth_year': 1800,
                'death_year': 1880,
                'id': 1
            },
            'language': 'en',
            'subjects': 'Fiction, Drama',
            'bookshelves': 'Classic Literature',
            'download_links': [
                {'mime_type': 'text/plain', 'url': 'http://example.com/book.txt'}
            ]
        }

    def test_basic_response_structure(self):
        """Test basic API response structure"""
        with patch('models.get_books_from_db') as mock_db:
            # Mock the database response
            mock_db.return_value = (1, [self.mock_book])
            
            response = self.app.get('/get_books')
            
            self.assertEqual(response.status_code, 200)
            try:
                data = json.loads(response.data)
                self.assertIn('total_books', data)
                self.assertIn('books', data)
                self.assertIn('pagination', data)
            except json.JSONDecodeError as e:
                self.fail(f"Invalid JSON response: {response.data}")

    def test_pagination(self):
        """Test pagination functionality"""
        with patch('models.get_books_from_db') as mock_db:
            # Create multiple mock books
            mock_books = [self.mock_book.copy() for _ in range(30)]
            mock_db.return_value = (30, mock_books[:25])  # Return first 25
            
            response = self.app.get('/get_books')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(len(data['books']) <= 25)
            self.assertEqual(data['pagination']['per_page'], 25)

    def test_filter_by_language(self):
        """Test filtering by language"""
        with patch('models.get_books_from_db') as mock_db:
            mock_book = self.mock_book.copy()
            mock_book['language'] = 'en'
            mock_db.return_value = (1, [mock_book])
            
            response = self.app.get('/get_books?language=en')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(all(book['language'] == 'en' for book in data['books']))

    def test_filter_by_topic(self):
        """Test topic filtering"""
        with patch('models.get_books_from_db') as mock_db:
            mock_book = self.mock_book.copy()
            mock_book['subjects'] = 'Children, Education'
            mock_db.return_value = (1, [mock_book])
            
            response = self.app.get('/get_books?topic=child')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(len(data['books']) > 0)

    def test_filter_by_author(self):
        """Test author filtering"""
        with patch('models.get_books_from_db') as mock_db:
            mock_book = self.mock_book.copy()
            mock_book['author_info']['name'] = 'Shakespeare, William'
            mock_db.return_value = (1, [mock_book])
            
            response = self.app.get('/get_books?author=shake')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(len(data['books']) > 0)

    def test_multiple_filters(self):
        """Test multiple filter criteria"""
        with patch('models.get_books_from_db') as mock_db:
            mock_book = self.mock_book.copy()
            mock_book.update({
                'language': 'en',
                'subjects': 'Children, Education',
                'author_info': {'name': 'Shakespeare, William'}
            })
            mock_db.return_value = (1, [mock_book])
            
            response = self.app.get('/get_books?language=en&topic=child&author=shake')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(len(data['books']) > 0)

    @patch('models.get_books_from_db')
    def test_empty_results(self, mock_db):
        """Test handling of no results"""
        # Mock the database to return empty results
        mock_db.return_value = (0, [])
        
        response = self.app.get('/get_books?title=nonexistentbook123456')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['total_books'], 0)
        self.assertEqual(len(data['books']), 0)

    @patch('models.get_books_from_db')
    def test_invalid_parameters(self, mock_db):
        """Test handling of invalid parameters"""
        # Mock successful database response
        mock_db.return_value = (1, [self.mock_book])
        
        # Test invalid page number
        response = self.app.get('/get_books?page=0')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['pagination']['page'] >= 1)
        
        # Test invalid per_page
        response = self.app.get('/get_books?per_page=1000')
        data = json.loads(response.data)
        self.assertTrue(data['pagination']['per_page'] <= 100)

if __name__ == '__main__':
    unittest.main()