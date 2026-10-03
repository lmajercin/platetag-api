<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class DiscoverySession extends Model
{
    protected $fillable = [
        'user_id',
        'name',
        'is_default',
        'ended_at',
    ];

    protected function casts(): array
    {
        return [
            'is_default' => 'boolean',
            'ended_at'   => 'datetime',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function discoveries(): HasMany
    {
        return $this->hasMany(UserDiscoveredPlate::class, 'session_id');
    }
}
