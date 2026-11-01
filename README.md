# FoundIt Backend

## Description

FoundIt Backend is a RESTful API built with Flask for a lost-and-found application.

It lets users register and log in securely, report lost and found items, submit and review ownership claims, and receive possible matches between lost and found reports. It also sends emails for account verification and claim updates.

The API uses PostgreSQL, SQLAlchemy and Flask-Migrate. The React frontend is in the [FoundIt frontend](https://github.com/trizahn2002-source/foundit) repository.

## Features

- Register with email verification, log in with a one-time code, or sign in with Google
- Password recovery and account settings (display name, password, email change, account deletion)
- Create and manage lost and found reports, organized by category
- Search and filter items by type, category and status, with pagination
- Suggest possible matches between lost and found items
- Claims: finders approve or reject them, and approving one rejects the other pending claims
- Email notifications when a claim is received, approved or rejected
- Optional tips for finders through the M-Pesa sandbox
- Rate limiting on sensitive authentication actions
- Database migrations and seed data for development

## Technologies Used

- Python, Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Bcrypt, Flask-CORS
- PostgreSQL, Psycopg2
- Python-dotenv, Requests
- Google Auth (Google sign-in) and Gmail API (email delivery)
- M-Pesa (sandbox)
- Pipenv, Render (hosting)

## How to Run the Project

1. Clone the repository and go into the folder.

   ```bash
   git clone https://github.com/trizahn2002-source/foundit-backend.git
   cd foundit-backend
   ```

2. Install the dependencies.

   ```bash
   pipenv install
   ```

3. Create a PostgreSQL database and user, then create a `.env` file using `.env.example` as a guide.

   ```env
   DATABASE_URL=postgresql+psycopg2://foundit_user:your_password@localhost:5432/foundit_db
   SECRET_KEY=your_secret_key
   ```

4. Make sure PostgreSQL is running.

   ```bash
   sudo service postgresql start
   ```

5. Apply the database migrations and add seed data.

   ```bash
   pipenv run flask --app app db upgrade
   pipenv run python seed.py
   ```

6. Start the Flask server. The API will be available at `http://localhost:5555`.

   ```bash
   pipenv run python app.py
   ```

7. Start the frontend from the [frontend repository](https://github.com/trizahn2002-source/foundit) with `npm run dev`. It cannot load data unless this server is running.

## Environment Variables

Copy `.env.example` to `.env` and fill in your own values. Never commit the `.env` file.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Secret used to sign sessions |
| `FRONTEND_URL` | Frontend address, used for links in emails |
| `SESSION_COOKIE_SECURE` | Set to `true` when served over HTTPS |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID for Google sign-in |
| `EMAIL_PROVIDER` | Set to `gmail` |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER_EMAIL` | Gmail API credentials |
| `OTP_TEST_MODE`, `OTP_TEST_EMAIL` | When test mode is on, all emails go to the test address |
| `EMAIL_CHANGE_SMTP_*`, `EMAIL_CHANGE_FROM` | SMTP settings for email-change codes |
| `MPESA_*` | M-Pesa sandbox settings for tips |

## API Endpoints

- **API:** `GET /api` — check that the API is running
- **Authentication:** `POST /api/register`, `POST /api/verify-email`, `POST /api/resend-verification`, `POST /api/login`, `POST /api/login/verify-otp`, `POST /api/login/resend-otp`, `POST /api/auth/google`, `POST /api/logout`, `GET /api/check_session`, `GET /api/csrf-token`
- **Password recovery:** `POST /api/forgot-password`, `POST /api/validate-reset-token`, `POST /api/reset-password`
- **Account:** `GET /api/account`, `PATCH /api/account/display-name`, `POST /api/account/change-password`, `POST /api/account/email-change/request`, `POST /api/account/email-change/confirm`, `POST /api/account/delete`
- **Categories:** `GET` and `POST /api/categories`, `PATCH` and `DELETE /api/categories/<category_id>`
- **Items:** `GET` and `POST /api/items` (list supports search, type, category, status and pagination), `GET`, `PATCH` and `DELETE /api/items/<item_id>`
- **Possible matches:** `GET /api/items/<item_id>/matches`
- **Claims:** `POST` and `GET /api/items/<item_id>/claims`, `GET /api/claims/action-required`, `PATCH /api/claims/<claim_id>` (approve or reject)
- **Dashboard:** `GET /api/users/<user_id>/items`, `GET /api/users/<user_id>/claims`
- **Users:** `PATCH` or `PUT` and `DELETE /api/users/<user_id>`
- **Tips:** `POST /api/items/<item_id>/tips`, `GET /api/tips/<tip_id>/status`

## Matching Logic

A possible match must:

- Be the opposite report type (`lost` or `found`)
- Belong to the same category
- Have an active status
- Belong to a different user
- Share at least two meaningful keywords

Reports more than seven days apart are excluded. Location improves the match score but does not exclude items. Stronger matches are returned first.

## Database Models

- **User:** username, display name, email, password hash, email verification date
- **Category:** name
- **Item:** title, description, type (lost or found), status (active, claimed or resolved), location, coordinates, date, image, category, owner
- **Claim:** message, status (pending, approved or rejected), optional contact details shared by the finder, user, item. A user can claim an item only once.
- **Tip:** amount, status, item, tipper, finder
- **Authentication models:** email verification codes, login one-time codes, password reset tokens, Google identities, pending email changes and rate limit counters

## Future Improvements

- Replace the sandbox M-Pesa tips with live payments
- Notify users when new possible matches are found
- Tune matching rules using more sample data
- Add more automated tests

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