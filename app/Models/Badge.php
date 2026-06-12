<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use App\Models\Plate;

class Badge extends Model
{
    protected $fillable = [
        'slug', 'name', 'description', 'type', 'threshold',
        'icon', 'sort_order', 'is_active',
    ];

    protected $casts = [
        'is_active' => 'boolean',
        'threshold' => 'integer',
    ];

    public function regions(): BelongsToMany
    {
        return $this->belongsToMany(Region::class, 'badge_regions');
    }

    public function plates(): BelongsToMany
    {
        return $this->belongsToMany(Plate::class, 'badge_plates');
    }

    public function userBadges(): HasMany
    {
        return $this->hasMany(UserBadge::class);
    }

    public function isGeographic(): bool
    {
        return $this->type === 'geographic';
    }

    public function isMilestone(): bool
    {
        return $this->type === 'milestone';
    }

    public function isCollection(): bool
    {
        return $this->type === 'collection';
    }
}
