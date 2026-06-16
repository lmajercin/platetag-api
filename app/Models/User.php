<?php

namespace App\Models;

use App\Notifications\MobilePasswordReset;
use App\Notifications\MobileVerifyEmail;
use Database\Factories\UserFactory;
use Filament\Models\Contracts\FilamentUser;
use Filament\Panel;
use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Jeffgreco13\FilamentBreezy\Traits\TwoFactorAuthenticatable;
use Laravel\Sanctum\HasApiTokens;

class User extends Authenticatable implements FilamentUser, MustVerifyEmail
{
    use HasApiTokens, HasFactory, Notifiable, TwoFactorAuthenticatable;

    protected $fillable = [
        'name',
        'email',
        'password',
        // is_admin intentionally excluded — set only via forceFill() or direct assignment in admin tooling
    ];

    protected $hidden = [
        'password',
        'remember_token',
    ];

    protected function casts(): array
    {
        return [
            'email_verified_at'  => 'datetime',
            'password'           => 'hashed',
            'is_admin'           => 'boolean',
            // is_premium, is_founding_member, and promo_expires_at are intentionally excluded
            // from $fillable. They must only be set via forceFill() in PurchaseController,
            // AuthController, or PromoController. Mass assignment must never reach these fields.
            'is_premium'         => 'boolean',
            'is_founding_member' => 'boolean',
            'premium_granted_at' => 'datetime',
            'promo_expires_at'   => 'datetime',
        ];
    }

    public function sendPasswordResetNotification($token): void
    {
        $this->notify(new MobilePasswordReset($token));
    }

    public function sendEmailVerificationNotification(): void
    {
        $this->notify(new MobileVerifyEmail());
    }

    public function canAccessPanel(Panel $panel): bool
    {
        return $this->is_admin === true;
    }

    public function socialAccounts(): HasMany
    {
        return $this->hasMany(SocialAccount::class);
    }

    public function purchases(): HasMany
    {
        return $this->hasMany(Purchase::class);
    }

    public function promoRedemptions(): HasMany
    {
        return $this->hasMany(PromoCodeRedemption::class);
    }
}
