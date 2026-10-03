<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class GroupDiscovery extends Model
{
    public $timestamps = false; // Using discovered_at instead

    protected $fillable = [
        'group_id',
        'user_id',
        'plate_id',
        'discovered_at',
    ];

    protected $casts = [
        'discovered_at' => 'datetime',
    ];

    /**
     * Get the group this discovery belongs to.
     */
    public function group(): BelongsTo
    {
        return $this->belongsTo(Group::class);
    }

    /**
     * Get the user who made this discovery.
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Get the plate that was discovered.
     */
    public function plate(): BelongsTo
    {
        return $this->belongsTo(Plate::class);
    }
}
