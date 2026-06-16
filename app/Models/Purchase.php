<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Purchase extends Model
{
    protected $fillable = [
        'user_id',
        'platform',
        'product_id',
        'transaction_id',
        'raw_receipt',
        'verified_at',
    ];

    protected function casts(): array
    {
        return [
            // Automatically AES-256 encrypted at rest using APP_KEY.
            // Never hash — original value must be recoverable for dispute resolution.
            'raw_receipt' => 'encrypted',
            'verified_at' => 'datetime',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
