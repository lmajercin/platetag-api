<?php
/**
 * Phase 2 HTTP Endpoint Testing for Groups Feature
 * Tests all 17 REST API endpoints
 * Run with: php tests/manual/test_groups_phase2_http.php
 */

require __DIR__ . '/../../vendor/autoload.php';

$app = require_once __DIR__ . '/../../bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use Illuminate\Support\Facades\Http;

// Get test user and generate token
$user = \App\Models\User::first();
$token = $user->createToken('phase2-test')->plainTextToken;

$baseUrl = 'http://127.0.0.1:8000/api/v1/auth';
$authHeader = ['Authorization' => "Bearer {$token}"];

echo "=== PHASE 2: HTTP ENDPOINT TESTING ===\n";
echo "Testing as: {$user->email} (ID {$user->id})\n";
echo "Base URL: {$baseUrl}\n\n";

$passed = 0;
$failed = 0;
$groupId = null;
$inviteToken = null;

// Helper function to test endpoint
function testEndpoint($name, $method, $url, $headers, $body = null) {
    global $passed, $failed;
    
    echo "Test: {$name}\n";
    echo str_repeat('-', 50) . "\n";
    
    try {
        $request = Http::withHeaders($headers)->withOptions(['allow_redirects' => false]);
        
        $response = match(strtoupper($method)) {
            'GET' => $request->get($url),
            'POST' => $request->post($url, $body ?? []),
            'PUT' => $request->put($url, $body ?? []),
            'PATCH' => $request->patch($url, $body ?? []),
            'DELETE' => $request->delete($url),
            default => throw new Exception("Unknown method: {$method}")
        };
        
        $statusCode = $response->status();
        $success = $response->successful();
        
        if ($success) {
            echo "✓ PASSED - Status: {$statusCode}\n";
            $passed++;
        } else {
            echo "✗ FAILED - Status: {$statusCode}\n";
            $failed++;
        }
        
        // Show response preview
        $json = $response->json();
        $body = $response->body();
        
        if ($json) {
            $preview = json_encode($json, JSON_PRETTY_PRINT);
            $lines = explode("\n", $preview);
            $previewLines = array_slice($lines, 0, 10);
            echo "Response Preview:\n" . implode("\n", $previewLines);
            if (count($lines) > 10) {
                echo "\n... (" . (count($lines) - 10) . " more lines)";
            }
            echo "\n";
        } elseif ($body) {
            echo "Response Body (non-JSON):\n" . substr($body, 0, 200) . "\n";
        } else {
            echo "Response: (empty)\n";
        }
        
        echo "\n";
        return ['success' => $success, 'response' => $response];
        
    } catch (Exception $e) {
        echo "✗ FAILED - Exception: {$e->getMessage()}\n\n";
        $failed++;
        return ['success' => false, 'response' => null];
    }
}

echo "=== 1. GROUP MANAGEMENT (9 endpoints) ===\n\n";

// Test 01: List My Groups
$result = testEndpoint(
    '01 - List My Groups',
    'GET',
    "{$baseUrl}/groups",
    $authHeader
);

// Test 02: Create Group
$result = testEndpoint(
    '02 - Create Group',
    'POST',
    "{$baseUrl}/groups",
    $authHeader,
    [
        'name' => 'HTTP Test Group',
        'is_public' => true,
        'country' => 'US',
        'member_cap' => 15,
        'game_mode' => 'lifetime'
    ]
);
if ($result['success']) {
    $json = $result['response']->json();
    $groupId = $json['group']['id'] ?? null;
    echo ">>> Created Group ID: {$groupId}\n\n";
}

// Test 03: Get Group Details
if ($groupId) {
    testEndpoint(
        '03 - Get Group Details',
        'GET',
        "{$baseUrl}/groups/{$groupId}",
        $authHeader
    );
} else {
    echo "⚠ Skipping Test 03 - No group ID available\n\n";
}

// Test 04: Update Group
if ($groupId) {
    testEndpoint(
        '04 - Update Group',
        'PATCH',
        "{$baseUrl}/groups/{$groupId}",
        $authHeader,
        [
            'name' => 'HTTP Test Group - UPDATED',
            'member_cap' => 20
        ]
    );
} else {
    echo "⚠ Skipping Test 04 - No group ID available\n\n";
}

// Test 05: List Group Members
if ($groupId) {
    testEndpoint(
        '05 - List Group Members',
        'GET',
        "{$baseUrl}/groups/{$groupId}/members",
        $authHeader
    );
} else {
    echo "⚠ Skipping Test 05 - No group ID available\n\n";
}

echo "=== 2. INVITES (3 endpoints) ===\n\n";

// Test 10: Generate Invite Token
if ($groupId) {
    echo "DEBUG: Calling POST {$baseUrl}/groups/{$groupId}/invite\n";
    $result = testEndpoint(
        '10 - Generate Invite Token',
        'POST',
        "{$baseUrl}/groups/{$groupId}/invite",
        array_merge($authHeader, ['Accept' => 'application/json', 'Content-Type' => 'application/json']),
        [
            'days_valid' => 30
        ]
    );
    if ($result['success']) {
        $json = $result['response']->json();
        $inviteToken = $json['invite_token'] ?? null;
        echo ">>> Generated Token: {$inviteToken}\n\n";
    } else {
        echo "DEBUG: Failed with status " . $result['response']->status() . "\n";
        echo "DEBUG: Response: " . substr($result['response']->body(), 0, 200) . "\n\n";
    }
} else {
    echo "⚠ Skipping Test 10 - No group ID available\n\n";
}

// Test 11: Preview Invite (no auth required)
if ($inviteToken) {
    testEndpoint(
        '11 - Preview Invite',
        'GET',
        "http://127.0.0.1:8000/api/v1/groups/join/{$inviteToken}",
        ['Accept' => 'application/json']
    );
} else {
    echo "⚠ Skipping Test 11 - No invite token available\n\n";
}

// Test 12: Join Group via Invite (using second test user)
$user2 = \App\Models\User::where('id', '!=', $user->id)->first();
if ($user2 && $inviteToken) {
    $token2 = $user2->createToken('phase2-test-user2')->plainTextToken;
    testEndpoint(
        '12 - Join Group via Invite',
        'POST',
        "http://127.0.0.1:8000/api/v1/groups/join/{$inviteToken}",
        ['Authorization' => "Bearer {$token2}"]
    );
} else {
    echo "⚠ Skipping Test 12 - No second user or invite token available\n\n";
}

echo "=== 3. LEADERBOARDS (3 endpoints) ===\n\n";

// Test 13: Group Leaderboard (Lifetime)
if ($groupId) {
    testEndpoint(
        '13 - Group Leaderboard (Lifetime)',
        'GET',
        "{$baseUrl}/groups/{$groupId}/leaderboard?mode=lifetime",
        $authHeader
    );
} else {
    echo "⚠ Skipping Test 13 - No group ID available\n\n";
}

// Test 14: Member Plates List
if ($groupId) {
    testEndpoint(
        '14 - Member Plates List',
        'GET',
        "{$baseUrl}/groups/{$groupId}/members/{$user->id}/plates",
        $authHeader
    );
} else {
    echo "⚠ Skipping Test 14 - No group ID available\n\n";
}

// Test 15: State Map
if ($groupId) {
    testEndpoint(
        '15 - State Map',
        'GET',
        "{$baseUrl}/groups/{$groupId}/state-map",
        $authHeader
    );
} else {
    echo "⚠ Skipping Test 15 - No group ID available\n\n";
}

echo "=== 4. GAMES (2 endpoints) ===\n\n";

// Test 16: List Games
if ($groupId) {
    testEndpoint(
        '16 - List Games',
        'GET',
        "{$baseUrl}/groups/{$groupId}/games",
        $authHeader
    );
} else {
    echo "⚠ Skipping Test 16 - No group ID available\n\n";
}

// Test 17: Create Game
if ($groupId) {
    testEndpoint(
        '17 - Create Game',
        'POST',
        "{$baseUrl}/groups/{$groupId}/games",
        $authHeader,
        [
            'game_type' => '50_states',
            'country' => 'US',
            'target_count' => 50
        ]
    );
} else {
    echo "⚠ Skipping Test 17 - No group ID available\n\n";
}

echo "=== 5. MEMBER MANAGEMENT (3 destructive endpoints - testing last) ===\n\n";

// Test 06: Transfer Leadership
if ($groupId && $user2) {
    testEndpoint(
        '06 - Transfer Leadership',
        'PATCH',
        "{$baseUrl}/groups/{$groupId}/leader",
        $authHeader,
        ['new_leader_id' => $user2->id]
    );
} else {
    echo "⚠ Skipping Test 06 - No group or second user available\n\n";
}

// Test 07: Remove Member (transfer leadership back first)
if ($groupId && $user2) {
    // First transfer back to original leader
    $token2 = $user2->createToken('transfer-back')->plainTextToken;
    Http::withHeaders(['Authorization' => "Bearer {$token2}"])
        ->patch("{$baseUrl}/groups/{$groupId}/leader", ['new_leader_id' => $user->id]);
    
    testEndpoint(
        '07 - Remove Member',
        'DELETE',
        "{$baseUrl}/groups/{$groupId}/members/{$user2->id}",
        $authHeader
    );
} else {
    echo "⚠ Skipping Test 07 - No group or second user available\n\n";
}

// Test 08: Leave Group (skipping - would break remaining tests)
echo "Test: 08 - Leave Group\n";
echo str_repeat('-', 50) . "\n";
echo "⚠ SKIPPED - Would break remaining tests\n";
echo "Endpoint: POST {$baseUrl}/groups/{$groupId}/leave\n\n";

// Test 09: Delete Group (skipping - destructive)
echo "Test: 09 - Delete Group\n";
echo str_repeat('-', 50) . "\n";
echo "⚠ SKIPPED - Destructive test (can run manually)\n";
echo "Endpoint: DELETE {$baseUrl}/groups/{$groupId}\n\n";

echo "=== TEST SUMMARY ===\n";
echo "✓ Passed: {$passed}\n";
echo "✗ Failed: {$failed}\n";
echo "⚠ Skipped: 2 (destructive tests)\n";
echo "\n";

if ($failed === 0) {
    echo "🎉 All tested endpoints working correctly!\n";
} else {
    echo "⚠ Some endpoints failed - review output above.\n";
}

echo "\n";
echo "Created Group ID: " . ($groupId ?? 'N/A') . "\n";
echo "Invite Token: " . ($inviteToken ?? 'N/A') . "\n";
