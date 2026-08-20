<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Employees table — foundation for Phase 4.
 * Full HR management (payroll, leave, schedule) belongs to later phases.
 * employee_number is the business identifier (not the PK).
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('employees', function (Blueprint $table) {
            $table->id();
            $table->string('employee_number', 30)->unique();
            $table->string('first_name', 80);
            $table->string('middle_name', 80)->nullable();
            $table->string('last_name', 80);
            $table->string('suffix', 10)->nullable();
            $table->foreignId('branch_id')->nullable()->constrained()->nullOnDelete();
            $table->foreignId('department_id')->nullable()->constrained()->nullOnDelete();
            $table->string('position', 100)->nullable();
            $table->string('employment_status', 20)->default('active')->index(); // active, inactive, resigned
            $table->date('date_hired')->nullable();
            $table->string('email', 120)->nullable()->unique();
            $table->string('contact_number', 30)->nullable();
            $table->string('status', 10)->default('active')->index();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('employees');
    }
};
