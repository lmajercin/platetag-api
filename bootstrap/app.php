<?php

use App\Console\Commands\ExpirePromoAccess;
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        // Sanctum stateful middleware — enables cookie/session auth for web SPA
        // requests from SANCTUM_STATEFUL_DOMAINS (platetag.app).
        $middleware->api(prepend: [
            \Laravel\Sanctum\Http\Middleware\EnsureFrontendRequestsAreStateful::class,
        ]);

        // Trust Cloudflare IP ranges as upstream proxies.
        // Cloudflare sits in front of A2 Hosting and forwards the real client IP
        // via X-Forwarded-For. Without trusting these ranges, all rate limiting
        // collapses to a single IP (Cloudflare's) and real client IPs are invisible.
        // Do NOT add '*' — it allows any client to spoof X-Forwarded-For.
        // Source: https://www.cloudflare.com/ips/ (last updated 2026-05-30)
        $middleware->trustProxies(
            at: [
                // Cloudflare IPv4
                '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22',
                '103.31.4.0/22',   '141.101.64.0/18', '108.162.192.0/18',
                '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22',
                '198.41.128.0/17', '162.158.0.0/15',  '104.16.0.0/13',
                '104.24.0.0/14',   '172.64.0.0/13',   '131.0.72.0/22',
                // Cloudflare IPv6
                '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32',
                '2405:b500::/32', '2405:8100::/32', '2a06:98c0::/29',
                '2c0f:f248::/32',
                // Local / private network (keep for non-Cloudflare environments)
                '127.0.0.1', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
            ],
            headers: \Illuminate\Http\Request::HEADER_X_FORWARDED_FOR |
                     \Illuminate\Http\Request::HEADER_X_FORWARDED_HOST |
                     \Illuminate\Http\Request::HEADER_X_FORWARDED_PORT |
                     \Illuminate\Http\Request::HEADER_X_FORWARDED_PROTO,
        );
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        // Return 401 JSON for unauthenticated requests instead of attempting
        // to redirect to a named 'login' route (which doesn't exist in an API-only app).
        $exceptions->render(function (\Illuminate\Auth\AuthenticationException $e, Request $request) {
            return response()->json(['message' => 'Unauthenticated.'], 401);
        });
        // Catch the RouteNotFoundException thrown when Authenticate middleware tries
        // route('login') before the AuthenticationException propagates.
        $exceptions->render(function (\Symfony\Component\Routing\Exception\RouteNotFoundException $e, Request $request) {
            if (str_starts_with($request->path(), 'api/')) {
                return response()->json(['message' => 'Unauthenticated.'], 401);
            }
        });
    })
    ->booted(function () {
        // Auth endpoints: 10 attempts per minute per IP
        RateLimiter::for('auth', function (Request $request) {
            return Limit::perMinute(10)->by($request->ip());
        });

        // Public submission endpoints: 5 per minute per IP
        RateLimiter::for('submissions', function (Request $request) {
            return Limit::perMinute(5)->by($request->ip());
        });

        // General API: 120 requests per minute per user or IP
        RateLimiter::for('api', function (Request $request) {
            return $request->user()
                ? Limit::perMinute(120)->by($request->user()->id)
                : Limit::perMinute(60)->by($request->ip());
        });
    })
    ->withSchedule(function (\Illuminate\Console\Scheduling\Schedule $schedule): void {
        // Revoke is_premium for users whose windowed promo access has lapsed.
        // Runs daily at 02:00 server time. Only touches users with promo_expires_at in the past
        // and no active IAP purchase — paid users are never affected.
        $schedule->command(ExpirePromoAccess::class)->dailyAt('02:00');
    })
    ->create();
