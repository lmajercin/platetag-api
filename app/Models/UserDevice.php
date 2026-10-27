<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

// @Audit GO: 2026-10-27 — Build 91 (5a). Push notification token storage.
// One row per user per platform. Composite unique (user_id, platform) enforced at DB level.
// updateOrCreate(['user_id', 'platform']) handles token refresh on reinstall without duplicates.

class UserDevice extends Model
{
    protected $fillable = [
        'user_id',
        'push_token',
        'platform',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
