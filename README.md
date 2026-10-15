# FoundIt Backend

## Description

FoundIt Backend is a RESTful API built with Flask for a lost-and-found application.

The API allows users to report lost and found items, view item reports, submit claims for found items, view their own reports and claims, and receive possible matches between lost and found reports.

Possible matches are generated using details such as item category, shared keywords, report dates and location distance.

The application uses PostgreSQL for data storage, SQLAlchemy for database management and Flask-Migrate for database migrations.

## Features

- Create and manage lost and found item reports
- Organize items by category
- Submit claims for found items
- View claims
- View items reported by a user
- View claims submitted by a user
- Suggest possible matches between lost and found items
- Match items using category, keywords, report dates and location distance
- Support item statuses such as active, claimed and resolved
- Support claim statuses such as pending, approved and rejected
- PostgreSQL database integration
- Database migrations using Flask-Migrate
- Seed data for development
- JSON error responses and appropriate HTTP status codes

## Technologies Used

- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- Flask-Migrate
- Flask-Bcrypt
- Flask-CORS
- PostgreSQL
- Psycopg2
- Python-dotenv
- Pipenv

## How to Run the Project

1. Clone the repository.

   ```bash
    git clone https://github.com/trizahn2002-source/foundit-backend.git
   ```

2. Navigate into the project folder.

   ```bash
   cd foundit-backend
   ```

3. Install the project dependencies.

   ```bash
   pipenv install
   ```

4. Create a PostgreSQL database and database user.

5. Create a `.env` file using `.env.example` as a guide.

   ```env
   DATABASE_URL=postgresql+psycopg2://foundit_user:your_password@localhost:5432/foundit_db
   SECRET_KEY=your_secret_key
   ```

6. Make sure PostgreSQL is running.

   ```bash
   sudo service postgresql start
   ```

7. Apply the existing database migrations.

   ```bash
   pipenv run flask --app app db upgrade
   ```

8. Add seed data.

   ```bash
   pipenv run python seed.py
   ```

9. Start the Flask server.

   ```bash
   pipenv run python app.py
   ```

10. The API will be available at:

   ```text
   http://localhost:5555
   ```

## API Endpoints

### API

- `GET /api` — Check that the FoundIt API is running

### Categories

- `GET /api/categories` — View all item categories

### Items

- `GET /api/items` — View all lost and found item reports
- `GET /api/items/<item_id>` — View a specific item
- `POST /api/items` — Create a new lost or found item report
- `PATCH /api/items/<item_id>` — Update an existing item report
- `DELETE /api/items/<item_id>` — Delete an item report

### Possible Matches

- `GET /api/items/<item_id>/matches` — View possible lost/found matches for an item

### Claims

- `POST /api/items/<item_id>/claims` — Submit a claim for an item
- `GET /api/items/<item_id>/claims` — View claims submitted for a specific item
- `GET /api/claims/mine` — View claims belonging to the current user
- `GET /api/claims/<claim_id>` — View a specific claim
- `PATCH /api/claims/<claim_id>` — Update a claim
- `DELETE /api/claims/<claim_id>` — Delete a claim

### Dashboard

- `GET /api/users/<user_id>/items` — View items reported by a user
- `GET /api/users/<user_id>/claims` — View claims submitted by a user

## Matching Logic

The possible matches endpoint compares lost and found item reports using a combination of rules.

A possible match must:

- Be the opposite report type (`lost` or `found`)
- Belong to the same category
- Have an active status
- Belong to a different user
- Share at least two meaningful keywords

Reports that are more than seven days apart are currently excluded.

Location is used to improve the match score rather than automatically excluding items that are farther apart.

Matches are scored and returned with stronger matches appearing first.

The matching rules may be adjusted in future after testing with more sample data.

## Authentication and Access Control

Some backend routes are already structured to use session-based authentication.

However, the complete authentication implementation has not yet been integrated into the current backend.

The dashboard endpoints currently use the `user_id` supplied in the route for development and testing.

Once authentication is fully integrated, these endpoints should use the logged-in user's identity instead of relying on a user ID supplied in the URL.

## Database Models

### User

Stores user account information including:

- Username
- Email
- Password hash
- Creation date

### Category

Stores the categories used to organize lost and found items.

### Item

Stores lost and found item reports including:

- Title
- Description
- Lost or found type
- Status
- Location
- Latitude
- Longitude
- Report date
- Image URL
- Category
- User
- Creation date

### Claim

Stores claims submitted for found items including:

- Claim message
- Claim status
- User
- Item
- Creation date

## Future Improvements

- Complete authentication integration
- Use authenticated users for dashboard endpoints
- Improve authorization across protected routes
- Tune matching rules using more sample data
- Improve match scoring
- Complete frontend and backend integration across all features
- Add more automated tests
- Deploy the application

## Collaborators

- [Trizah Njeri](https://github.com/trizahn2002-source) — Scrum Master; Flask application setup, configuration, database setup, migrations, seed data, pull request merging and frontend–Flask integration
- [Wesley Were](https://github.com/WesleyWanga) — Authentication and Users; User model, password hashing, signup, login, logout, session checking and Login/Register pages
- [Samuel Mwaura](https://github.com/kimz-art) — Items and Categories; Item and Category models, item creation/editing/deletion, search and filters, Home page and Report page
- [Regan Njeru](https://github.com/toshregan94-hub) — Claims; Claim model, claim submission, approve/reject functionality, claim rules and claim form integration on Item Details
- [Abigail Tandiwe](https://github.com/tandisimelane-15) — Matches, Dashboard and Testing; matching rules endpoint, My Items, My Claims, dashboard integration, error handling, Postman testing of backend endpoints and backend README

## How to Contribute

Pull requests are welcome.

For major changes, please discuss the proposed changes with the team before implementation.

## License

MIT License

Copyright (c) 2026 FoundIt Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files, to deal in the Software
without restriction, including without limitation the rights to use, copy,
modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contact

For questions or contributions, please contact the FoundIt development team through the project repository.