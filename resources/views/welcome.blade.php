<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="PlateTag — The license plate collecting app. Coming soon.">
    <title>PlateTag — Coming Soon</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background-color: #0F172A;
            color: #F8FAFC;
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            text-align: center;
        }

        .logo {
            max-width: 280px;
            width: 100%;
            height: auto;
            border-radius: 16px;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }

        .badge {
            display: inline-block;
            background-color: #1E293B;
            border: 1px solid #334155;
            color: #94A3B8;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            padding: 0.35rem 1rem;
            border-radius: 999px;
            margin-bottom: 1.25rem;
        }

        h1 {
            font-size: clamp(2.5rem, 8vw, 4rem);
            font-weight: 800;
            color: #F89E0B;
            line-height: 1.1;
            margin-bottom: 1rem;
        }

        .tagline {
            font-size: 1.125rem;
            color: #94A3B8;
            max-width: 380px;
            line-height: 1.6;
            margin-bottom: 2.5rem;
        }

        .divider {
            width: 48px;
            height: 3px;
            background-color: #F97316;
            border-radius: 99px;
            margin: 0 auto 2.5rem;
        }

        .contact-label {
            font-size: 0.8rem;
            color: #475569;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .contact-link {
            color: #F89E0B;
            text-decoration: none;
            font-size: 1rem;
            font-weight: 600;
            transition: color 0.2s;
        }

        .contact-link:hover {
            color: #F97316;
        }
    </style>
</head>
<body>
    <img src="/platetag-logo.png" alt="PlateTag Logo" class="logo">

    <div class="badge">Coming Soon</div>

    <h1>PlateTag</h1>

    <p class="tagline">The license plate collecting app. Spot them, tag them, collect them all.</p>

    <div class="divider"></div>

    <p class="contact-label">Contact</p>
    <a href="mailto:info@platetag.app" class="contact-link">info@platetag.app</a>
</body>
</html>
