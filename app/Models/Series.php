<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Series extends Model
{
    protected $fillable = [
        'name', 'slug', 'region_id', 'category_id',
        'year_start', 'year_end', 'description', 'is_active',
    ];

    protected $casts = ['is_active' => 'boolean'];

    public function region() { return $this->belongsTo(Region::class); }
    public function category() { return $this->belongsTo(Category::class); }
}
