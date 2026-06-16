<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PlateTag: Graphics Brief</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #1B2A3B;
      color: #E8EAF0;
      line-height: 1.7;
      padding: 2rem 1rem 4rem;
    }

    .container {
      max-width: 780px;
      margin: 0 auto;
    }

    header {
      text-align: center;
      padding: 3rem 0 2.5rem;
      border-bottom: 1px solid #2e4057;
      margin-bottom: 3rem;
    }

    header .wordmark {
      font-size: 2.4rem;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #ffffff;
    }

    header .wordmark span {
      color: #F5A623;
    }

    header .subtitle {
      margin-top: 0.5rem;
      font-size: 1rem;
      color: #9aafbf;
    }

    h2 {
      font-size: 1.15rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #F5A623;
      margin: 2.5rem 0 1rem;
    }

    p {
      color: #c8d4dc;
      margin-bottom: 0.9rem;
    }

    .card {
      background: #243347;
      border: 1px solid #2e4057;
      border-radius: 10px;
      padding: 1.5rem 1.75rem;
      margin-bottom: 1.25rem;
    }

    .card h3 {
      font-size: 1rem;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 0.4rem;
    }

    .card p {
      font-size: 0.93rem;
      color: #a8bac6;
      margin: 0;
    }

    ul.rules {
      list-style: none;
      padding: 0;
    }

    ul.rules li {
      padding: 0.65rem 0.75rem 0.65rem 1rem;
      border-left: 3px solid #F5A623;
      background: #243347;
      border-radius: 0 6px 6px 0;
      margin-bottom: 0.65rem;
      font-size: 0.94rem;
      color: #c8d4dc;
    }

    ul.rules li strong {
      color: #ffffff;
    }

    .deliverables-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }

    @media (max-width: 540px) {
      .deliverables-grid { grid-template-columns: 1fr; }
    }

    .deliverable-item {
      background: #243347;
      border: 1px solid #2e4057;
      border-radius: 8px;
      padding: 0.85rem 1rem;
      font-size: 0.88rem;
    }

    .deliverable-item .label {
      font-weight: 700;
      color: #ffffff;
      display: block;
      margin-bottom: 0.2rem;
    }

    .deliverable-item .spec {
      color: #7a96a8;
    }

    .tag {
      display: inline-block;
      background: #1B2A3B;
      border: 1px solid #2e4057;
      border-radius: 4px;
      padding: 0.15rem 0.55rem;
      font-size: 0.78rem;
      color: #9aafbf;
      margin: 0.15rem 0.15rem 0.15rem 0;
    }

    .tag.priority {
      border-color: #F5A623;
      color: #F5A623;
    }

    .palette-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 0.5rem;
    }

    .swatch {
      border-radius: 8px;
      padding: 1rem 1.25rem;
      min-width: 140px;
      flex: 1;
      text-align: center;
    }

    .swatch .swatch-name {
      font-weight: 700;
      font-size: 0.85rem;
      display: block;
      margin-bottom: 0.2rem;
    }

    .swatch .swatch-hex {
      font-size: 0.78rem;
      display: block;
      margin-bottom: 0.3rem;
    }

    .swatch .swatch-use {
      font-size: 0.76rem;
      display: block;
    }

    footer {
      margin-top: 4rem;
      padding-top: 1.5rem;
      border-top: 1px solid #2e4057;
      text-align: center;
      font-size: 0.82rem;
      color: #4a6070;
    }
  </style>
</head>
<body>
<div class="container">

  <header>
    <div class="wordmark">Plate<span>Tag</span></div>
    <div class="subtitle">Graphics Brief: App Icon &amp; Store Assets</div>
  </header>

  <!-- ── What Is PlateTag ── -->
  <h2>What Is PlateTag?</h2>
  <p>
    PlateTag is a mobile app for travelers who collect license plates. Spot a new state or province
    while road-tripping and tag it in your collection. It is a game of discovery, a travel journal,
    and a friendly competition all in one. The audience is road-trip enthusiasts, RV travelers, families
    on long drives, and anyone who has ever played the classic "license plate game."
  </p>
  <p>
    The feeling the app should evoke: <strong>the thrill of spotting something new on the open road.</strong>
    Fun, collectible, forward-moving energy. Think scratch-off map meets road-trip bingo.
  </p>

  <!-- ── Visual Concept Palette ── -->
  <h2>Visual Concepts to Draw From</h2>
  <p>
    The following are raw idea seeds, not a strict checklist. Incorporate what resonates and discard what doesn't.
    The best icon will likely combine two or three of these ideas rather than all of them.
  </p>

  <div class="card">
    <h3>License Plate — Primary Concept</h3>
    <p>
      A stylized license plate shape with the app name (or a bold abbreviation) prominent inside.
      The plate is the heart of the app. A clean, bold plate treatment that reads at small sizes
      is the strongest single-icon direction.
    </p>
  </div>

  <div class="card">
    <h3>Map Pin / Location Marker</h3>
    <p>
      Classic teardrop pin, but make it feel earned, not generic. Could anchor a plate graphic
      or serve as a secondary element suggesting "I was here."
    </p>
  </div>

  <div class="card">
    <h3>Green Circle with Checkmark</h3>
    <p>
      The universal signal of completion and success. Reinforces the collector/achievement mechanic:
      you tagged it, it's yours. Works well as a badge overlay on a plate or pin.
    </p>
  </div>

  <div class="card">
    <h3>Scenic Landscape with Road</h3>
    <p>
      Open highway receding into mountains, desert, or a wide sky. Captures the road-trip context
      and scope of the country being crossed. Works better in a banner / feature graphic than a square icon.
    </p>
  </div>

  <div class="card">
    <h3>Car Profile Highlighting the Plate</h3>
    <p>
      Front or rear silhouette of a vehicle with the license plate area emphasized, lit up, glowing,
      or zoomed in. Communicates the "spot it" gameplay instantly.
    </p>
  </div>

  <div class="card">
    <h3>Movement &amp; Action</h3>
    <p>
      Speed lines, motion blur on a passing car, a plate caught mid-frame as a vehicle drives past.
      The app is about spotting things in motion; the art should feel kinetic, not static.
    </p>
  </div>

  <div class="card">
    <h3>Color and Accomplishment</h3>
    <p>
      The checkmark or completion indicator should use color to carry the moment of success.
      A bold, saturated green on the check circle is the clearest signal of "earned it."
      Whatever color you land on, it should read as a reward, not a status label.
    </p>
  </div>

  <!-- ── Deliverables ── -->
  <h2>Required Deliverables</h2>
  <div class="deliverables-grid">
    <div class="deliverable-item">
      <span class="label">App Icon <span class="tag priority">Priority</span></span>
      <span class="spec">1024 × 1024 px, PNG, no rounded corners (OS applies mask). Must read at 60 × 60 px.</span>
    </div>
    <div class="deliverable-item">
      <span class="label">Google Play Feature Graphic <span class="tag priority">Priority</span></span>
      <span class="spec">1024 × 500 px, JPG or PNG. Landscape scene / banner treatment.</span>
    </div>
    <div class="deliverable-item">
      <span class="label">App Store Screenshots Background</span>
      <span class="spec">Background / scene layer at 1290 × 2796 px (iPhone 15 Pro Max). Optional but useful.</span>
    </div>
    <div class="deliverable-item">
      <span class="label">Source File</span>
      <span class="spec">AI, PSD, Figma, or SVG, layered so we can resize and adapt internally.</span>
    </div>
  </div>

  <!-- ── Designer Rules ── -->
  <h2>Designer Rules</h2>
  <ul class="rules">
    <li>
      <strong>The icon must read at 60 × 60 px.</strong>
      If the detail disappears at small size, it's the wrong design. Every submission must include
      a thumbnail preview at icon scale.
    </li>
    <li>
      <strong>Do not submit stock-photo composites or filter-over-photo treatments.</strong>
      All work must be original vector or illustrated art. No Unsplash backgrounds with a logo slapped on top.
    </li>
    <li>
      <strong>Avoid generic travel clichés.</strong>
      No suitcases, no generic globe icons, no airplane silhouettes. This is a road-trip app; keep
      the visual language on the ground.
    </li>
    <li>
      <strong>No text inside the icon except the plate itself.</strong>
      The word "PlateTag" is too long to be legible inside a 60 px icon. An abbreviated plate treatment
      ("PT" or a stylized plate shape) is acceptable; spelling out the full name is not.
    </li>
    <li>
      <strong>Deliver every size in the brief, not just the hero size.</strong>
      Include the 1024 px source, a 512 px export, a 192 px export, and a 60 px thumbnail in the final package.
    </li>
    <li>
      <strong>Provide at least two concept directions before finalizing.</strong>
      One plate-forward concept and one scene/action concept minimum. We will pick a direction
      before revisions begin.
    </li>
    <li>
      <strong>No AI-generated art as a final deliverable.</strong>
      AI sketches for ideation are fine. The submitted files must be human-crafted vector work
      that holds up to resizing without artifacts.
    </li>
    <li>
      <strong>Color palette must work on both dark and light backgrounds.</strong>
      The app ships in both dark mode and light mode. The icon will appear on home screens of
      every color. Test your palette on white, black, and mid-gray before submitting.
    </li>
    <li>
      <strong>Match the mood: fun and collectible, not corporate.</strong>
      This is a game for road-trip families. Bold, warm, slightly playful. Not a finance app.
      Not a logistics SaaS. Think collector trading card energy.
    </li>
  </ul>

  <!-- Palette Section -->
  <h2>App Color Palette</h2>
  <p>These are the app's existing colors. The icon and store graphics should feel at home alongside them.</p>

  <div class="palette-grid">
    <div class="swatch" style="background:#1B2A3B; border: 1px solid #2e4057;">
      <span class="swatch-name" style="color:#E8EAF0;">Deep Navy</span>
      <span class="swatch-hex" style="color:#7a96a8;">#1B2A3B</span>
      <span class="swatch-use" style="color:#4a6070;">Dark mode background</span>
    </div>
    <div class="swatch" style="background:#3DDC84;">
      <span class="swatch-name" style="color:#0d1f14;">Success Green</span>
      <span class="swatch-hex" style="color:#1a4030;">#3DDC84</span>
      <span class="swatch-use" style="color:#1a4030;">Tagged / earned state</span>
    </div>
    <div class="swatch" style="background:#F5A623;">
      <span class="swatch-name" style="color:#1a0e00;">Achievement Gold</span>
      <span class="swatch-hex" style="color:#4a300a;">#F5A623</span>
      <span class="swatch-use" style="color:#4a300a;">Reward, highlight</span>
    </div>
    <div class="swatch" style="background:#E8EAF0; border: 1px solid #c4ccd4;">
      <span class="swatch-name" style="color:#1B2A3B;">Plate White</span>
      <span class="swatch-hex" style="color:#4a5a68;">#E8EAF0</span>
      <span class="swatch-use" style="color:#4a5a68;">Light mode background / plate face</span>
    </div>
  </div>

  <footer>
    platetag.app — Internal brief, May 2026
  </footer>

</div>
</body>
</html>
