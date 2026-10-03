<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class UserDiscoveredPlate extends Model
{
    protected $table = 'user_discovered_plates';

    protected $fillable = [];

    protected function casts(): array
    {
        return [
            'discovered_at'      => 'datetime',
            'latitude'           => 'decimal:7',
            'longitude'          => 'decimal:7',
            'is_first_discovery' => 'boolean',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function plate(): BelongsTo
    {
        return $this->belongsTo(Plate::class);
    }

    public function session(): BelongsTo
    {
        return $this->belongsTo(DiscoverySession::class, 'session_id');
    }
}
