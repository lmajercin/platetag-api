<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SocialAccount extends Model
{
    protected $fillable = [
        'user_id',
        'provider',
        'provider_user_id',
        'provider_email',
        'token_expires_at',
        'apple_refresh_token',
    ];

    protected $casts = [
        'token_expires_at'    => 'datetime',
        // Encrypted at rest — requires APP_KEY. Only populated for provider='apple'.
        'apple_refresh_token' => 'encrypted',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
