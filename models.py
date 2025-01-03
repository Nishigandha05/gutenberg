import os
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

app = Flask(__name__)

# Database connection parameters
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Handle Heroku/Render style DATABASE_URL
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    url = urlparse(DATABASE_URL)
    db_config = {
        'dbname': url.path[1:],
        'user': url.username,
        'password': url.password,
        'host': url.hostname,
        'port': url.port
    }
else:
    # Local database configuration
    db_config = {
        "host": "127.0.0.1",
        "database": "gutenberg",
        "user": "nishigandha05",
        "password": 'nishi7456',
    }

#Function to retrieve data from database
def get_books_from_db(page=1, per_page=25, book_ids=None, languages=None, mime_types=None, 
                     topics=None, authors=None, titles=None):
    #connect to database
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor(cursor_factory = RealDictCursor)

    # Base query
    base_query = """
        SELECT 
            bb.title,
            bb.gutenberg_id,
            bb.download_count,
            json_build_object(
                'name', ba.name,
                'birth_year', ba.birth_year,
                'death_year', ba.death_year,
                'id', ba.id
            ) as author_info,
            bl.code as language,
            STRING_AGG(DISTINCT bs.name, ', ') as subjects,
            STRING_AGG(DISTINCT bbk.name, ', ') as bookshelves,
            json_agg(
                DISTINCT jsonb_build_object(
                    'mime_type', bf.mime_type,
                    'url', bf.url
                )
            ) as download_links
        FROM books_book as bb
        LEFT JOIN books_book_authors as bba 
            ON bb.gutenberg_id = bba.book_id
        LEFT JOIN books_author as ba 
            ON ba.id = bba.author_id
        LEFT JOIN books_book_languages as bbl 
            ON bb.gutenberg_id = bbl.book_id
        LEFT JOIN books_language as bl 
            ON bbl.language_id = bl.id
        LEFT JOIN books_book_subjects as bbs 
            ON bb.gutenberg_id = bbs.book_id
        LEFT JOIN books_subject as bs 
            ON bbs.subject_id = bs.id
        LEFT JOIN books_book_bookshelves as bbb
            ON bb.gutenberg_id = bbb.book_id
        LEFT JOIN books_bookshelf as bbk
            ON bbb.bookshelf_id = bbk.id
        LEFT JOIN books_format as bf
            ON bb.gutenberg_id = bf.book_id
        WHERE 1=1
    """
    
    # Build where clause for filtering
    where_conditions = []
    params = []

    if book_ids:
        where_conditions.append("bb.gutenberg_id = ANY(%s)")
        params.append(book_ids)

    if languages:
        where_conditions.append("bl.code = ANY(%s)")
        params.append(languages)

    if mime_types:
        where_conditions.append("bf.mime_type = ANY(%s)")
        params.append(mime_types)

    if topics:
        topic_conditions = []
        for topic in topics:
            topic_param = f"%{topic.lower()}%"
            topic_conditions.append("""
                (LOWER(bs.name) LIKE %s 
                OR LOWER(bbk.name) LIKE %s)
            """)
            params.extend([topic_param, topic_param])
        if topic_conditions:
            where_conditions.append(f"({' OR '.join(topic_conditions)})")

    if authors:
        author_conditions = []
        for author in authors:
            author_param = f"%{author.lower()}%"
            author_conditions.append("LOWER(ba.name) LIKE %s")
            params.append(author_param)
        if author_conditions:
            where_conditions.append(f"({' OR '.join(author_conditions)})")

    if titles:
        title_conditions = []
        for title in titles:
            title_param = f"%{title.lower()}%"
            title_conditions.append("LOWER(bb.title) LIKE %s")
            params.append(title_param)
        if title_conditions:
            where_conditions.append(f"({' OR '.join(title_conditions)})")

    # Add where conditions to base query
    if where_conditions:
        base_query += " AND " + " AND ".join(where_conditions)

    # Add GROUP BY for aggregations
    base_query += """
        GROUP BY 
            bb.title,
            bb.gutenberg_id,
            bb.download_count,
            ba.name,
            ba.birth_year,
            ba.death_year,
            ba.id,
            bl.code
    """

    # Get total count of unique books with filters
    count_query = """
        SELECT COUNT(DISTINCT bb.gutenberg_id) 
        FROM books_book as bb
        LEFT JOIN books_book_authors as bba ON bb.gutenberg_id = bba.book_id
        LEFT JOIN books_author as ba ON ba.id = bba.author_id
        LEFT JOIN books_book_languages as bbl ON bb.gutenberg_id = bbl.book_id
        LEFT JOIN books_language as bl ON bbl.language_id = bl.id
        LEFT JOIN books_book_subjects as bbs ON bb.gutenberg_id = bbs.book_id
        LEFT JOIN books_subject as bs ON bbs.subject_id = bs.id
        LEFT JOIN books_book_bookshelves as bbb ON bb.gutenberg_id = bbb.book_id
        LEFT JOIN books_bookshelf as bbk ON bbb.bookshelf_id = bbk.id
        LEFT JOIN books_format as bf ON bb.gutenberg_id = bf.book_id
        WHERE 1=1
    """
    
    if where_conditions:
        count_query += " AND " + " AND ".join(where_conditions)
    
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()['count']

    # Add ordering and pagination to main query
    base_query += " ORDER BY bb.download_count DESC NULLS LAST"
    base_query += " LIMIT %s OFFSET %s"
    
    # Add pagination parameters
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    cursor.execute(base_query, params)
    books = cursor.fetchall()

    cursor.close()
    connection.close()

    return total_count, books

@app.route('/get_books')
def get_books():
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)

        # Get filter parameters
        book_ids = request.args.getlist('book_id', type=int)
        languages = request.args.getlist('language')
        mime_types = request.args.getlist('mime_type')
        topics = request.args.getlist('topic')
        authors = request.args.getlist('author')
        titles = request.args.getlist('title')

        # Split comma-separated values
        languages = [lang for langs in languages for lang in langs.split(',')]
        mime_types = [mime for mimes in mime_types for mime in mimes.split(',')]
        topics = [topic.strip() for topics_list in topics for topic in topics_list.split(',')]
        authors = [author.strip() for authors_list in authors for author in authors_list.split(',')]
        titles = [title.strip() for titles_list in titles for title in titles_list.split(',')]

        # Validate parameters
        page = max(1, page)
        per_page = min(max(1, per_page), 100)

        # Get filtered books
        total_count, books = get_books_from_db(
            page=page,
            per_page=per_page,
            book_ids=book_ids if book_ids else None,
            languages=languages if languages else None,
            mime_types=mime_types if mime_types else None,
            topics=topics if topics else None,
            authors=authors if authors else None,
            titles=titles if titles else None
        )

        # Format the books data
        formatted_books = []
        for book in books:
            formatted_book = {
                'title': book['title'],
                'gutenberg_id': book['gutenberg_id'],
                'author': book['author_info'],
                'language': book['language'],
                'subjects': [s.strip() for s in book['subjects'].split(',')] if book['subjects'] else [],
                'bookshelves': [b.strip() for b in book['bookshelves'].split(',')] if book['bookshelves'] else [],
                'download_links': book['download_links'] if book['download_links'] else []
            }
            formatted_books.append(formatted_book)

        # Calculate pagination metadata
        total_pages = (total_count + per_page - 1) // per_page
        has_next = page < total_pages
        has_prev = page > 1

        response_data = {
            'total_books': total_count,
            'books': formatted_books,
            'filters_applied': {
                'book_ids': book_ids if book_ids else None,
                'languages': languages if languages else None,
                'mime_types': mime_types if mime_types else None,
                'topics': topics if topics else None,
                'authors': authors if authors else None,
                'titles': titles if titles else None
            },
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_prev': has_prev,
                'next_page': page + 1 if has_next else None,
                'prev_page': page - 1 if has_prev else None
            }
        }
        
        return jsonify(response_data)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Failed to fetch books'
        }), 500

@app.route('/')
def index():
    try:
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if not DATABASE_URL:
            return "DATABASE_URL not found", 500
            
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        connection.close()
        return "Database connection successful!"
    except Exception as e:
        return f"Database error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)