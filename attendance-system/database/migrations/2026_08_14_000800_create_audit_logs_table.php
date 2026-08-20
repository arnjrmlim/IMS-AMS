<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Audit logs — immutable record of important application actions.
 *
 * Logged events include: user login/logout, sync triggered, employee
 * created/updated, device viewed, settings changed, etc.
 *
 * Never logs: passwords, API keys, device comm keys.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('audit_logs', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->nullable()->constrained()->nullOnDelete();
            $table->string('action', 80)->index();      // e.g. 'login', 'sync_triggered'
            $table->string('module', 60)->nullable()->index(); // e.g. 'auth', 'devices', 'sync'
            $table->text('description');
            $table->string('ip_address', 45)->nullable();
            $table->text('user_agent')->nullable();
            $table->json('context')->nullable();        // safe extra metadata (no secrets)
            $table->timestamp('created_at')->useCurrent();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('audit_logs');
    }
};
