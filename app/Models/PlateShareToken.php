<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class PlateShareToken extends Model
{
    protected $fillable = [
        'created_by',
        'token',
        'plate_ids',      // JSON array of plate IDs
        'expires_at',
    ];

    protected $casts = [
        'expires_at' => 'datetime',
        'plate_ids'  => 'array',
    ];

    public function creator(): BelongsTo
    {
        return $this->belongsTo(User::class, 'created_by');
    }

    public function isExpired(): bool
    {
        return $this->expires_at->isPast();
    }
}
