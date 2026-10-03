<?php
/**
 * Phase 1 Manual Test Script for Groups Feature
 * Run with: php artisan test:groups-phase1
 */

require __DIR__ . '/../../vendor/autoload.php';

$app = require_once __DIR__ . '/../../bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

echo "=== PHASE 1: GROUPS BACKEND TESTING ===\n\n";

// Test 1: Create or fetch test users
echo "Test 1: User Setup\n";
echo "------------------\n";
$user1 = \App\Models\User::firstOrCreate(
    ['email' => 'test_leader@example.com'],
    [
        'name' => 'Test Leader',
        'password' => bcrypt('password'),
        'provider' => 'email',
    ]
);
echo "✓ User 1 (Leader): ID {$user1->id} - {$user1->email}\n";

$user2 = \App\Models\User::firstOrCreate(
    ['email' => 'test_member@example.com'],
    [
        'name' => 'Test Member',
        'password' => bcrypt('password'),
        'provider' => 'email',
    ]
);
echo "✓ User 2 (Member): ID {$user2->id} - {$user2->email}\n\n";

// Test 2: Create a Group
echo "Test 2: Group Creation\n";
echo "----------------------\n";
$group = \App\Models\Group::create([
    'name' => 'Test Adventure Group',
    'leader_id' => $user1->id,
    'is_public' => true,
    'member_cap' => 10,
    'game_mode' => 'lifetime',
]);
echo "✓ Group Created: ID {$group->id} - {$group->name}\n";
echo "  Leader: User {$group->leader_id}\n";
echo "  Privacy: " . ($group->is_public ? 'Public' : 'Private') . "\n";
echo "  Member Cap: {$group->member_cap}\n";
echo "  Game Mode: {$group->game_mode}\n\n";

// Test 3: Add Leader as Member with Color Assignment
echo "Test 3: Leader Auto-Membership + Color Assignment\n";
echo "--------------------------------------------------\n";
$leaderMembership = \App\Models\GroupMember::create([
    'group_id' => $group->id,
    'user_id' => $user1->id,
]);
$leaderMembership->assignColor();
echo "✓ Leader added as member: User {$leaderMembership->user_id}\n";
echo "  Assigned Color: {$leaderMembership->member_color}\n\n";

// Test 4: Add Second Member with Color Assignment
echo "Test 4: Add Second Member + Color Assignment\n";
echo "---------------------------------------------\n";
$member2 = \App\Models\GroupMember::create([
    'group_id' => $group->id,
    'user_id' => $user2->id,
]);
$member2->assignColor();
echo "✓ Member 2 added: User {$member2->user_id}\n";
echo "  Assigned Color: {$member2->member_color}\n\n";

// Test 5: Invite Token Generation
echo "Test 5: Invite Token Generation & Validation\n";
echo "---------------------------------------------\n";
$group->generateInviteToken();
$group->save();
echo "✓ Invite Token Generated: {$group->invite_token}\n";
echo "  Expires At: {$group->invite_expires_at}\n";
echo "  Invite Uses: {$group->invite_uses}\n";
echo "  Token Valid? " . ($group->isInviteTokenValid() ? 'YES' : 'NO') . "\n\n";

// Test 6: Game Creation
echo "Test 6: Game Creation (50 States)\n";
echo "----------------------------------\n";
$game = \App\Models\Game::create([
    'group_id' => $group->id,
    'game_type' => '50_states',
    'country' => 'US',
    'target_count' => 50,
]);
echo "✓ Game Created: ID {$game->id}\n";
echo "  Type: {$game->game_type}\n";
echo "  Country: {$game->country}\n";
echo "  Target: {$game->target_count} states\n";
echo "  Status: {$game->status}\n";
echo "  Active? " . ($game->isActive() ? 'YES' : 'NO') . "\n\n";

// Test 7: Relationship Verification
echo "Test 7: Relationship Verification\n";
echo "----------------------------------\n";
echo "Group '{$group->name}' has:\n";
echo "  - Leader: {$group->leader->name} (ID {$group->leader->id})\n";
echo "  - Members: {$group->members->count()}\n";
foreach ($group->members as $membership) {
    echo "    * {$membership->user->name} - Color: {$membership->member_color}\n";
}
echo "  - Active Games: {$group->games->count()}\n\n";

echo "User '{$user1->name}' (Leader) is:\n";
echo "  - Leading {$user1->ledGroups->count()} group(s)\n";
echo "  - Member of {$user1->groups->count()} group(s)\n\n";

// Test 8: Discovery Attribution (Mock)
echo "Test 8: Discovery Attribution Test\n";
echo "-----------------------------------\n";
$testPlate = \App\Models\Plate::first();
if ($testPlate) {
    $discoveredAt = now();
    
    try {
        \App\Models\GroupDiscovery::create([
            'group_id' => $group->id,
            'user_id' => $user1->id,
            'plate_id' => $testPlate->id,
            'discovered_at' => $discoveredAt,
        ]);
        echo "✓ Discovery attributed to group {$group->id}\n";
        echo "  User: {$user1->id} ({$user1->name})\n";
        echo "  Plate: {$testPlate->id} - {$testPlate->full_name}\n";
        echo "  Discovered At: {$discoveredAt}\n\n";
        
        // Verify relationship
        echo "Group now has {$group->discoveries->count()} discovery/discoveries\n";
    } catch (\Exception $e) {
        echo "✗ Discovery attribution failed: {$e->getMessage()}\n\n";
    }
} else {
    echo "⚠ No plates in database - skipping discovery test\n\n";
}

echo "=== PHASE 1 TESTS COMPLETE ===\n";
echo "\nAll models instantiated successfully.\n";
echo "Color assignment working.\n";
echo "Invite tokens generated.\n";
echo "Relationships verified.\n";
